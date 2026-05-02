import os

import anthropic
import psycopg2
from dotenv import load_dotenv

# load env vars and initialize clients
load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DB_DSN = os.environ.get("DB_DSN", "host=localhost dbname=trade_area_db")

# schema context passed to claude so it knows the table/column structure
SCHEMA = """
CREATE TABLE sites (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  geom GEOMETRY(Point, 4326) NOT NULL
);

CREATE TABLE trade_areas (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  geom GEOMETRY(Polygon, 4326) NOT NULL
);

CREATE TABLE census_tracts (
  gid      SERIAL PRIMARY KEY,
  statefp  VARCHAR(2),
  countyfp VARCHAR(3),
  tractce  VARCHAR(6),
  geoid    VARCHAR(11),
  geoidfq  VARCHAR(20),
  name     VARCHAR(7),
  namelsad VARCHAR(20),
  mtfcc    VARCHAR(5),
  funcstat VARCHAR(1),
  aland    DOUBLE PRECISION,
  awater   DOUBLE PRECISION,
  intptlat VARCHAR(11),
  intptlon VARCHAR(12),
  geom     GEOMETRY(MultiPolygon, 4326)
);

CREATE TABLE acs_data (
  geoid           TEXT PRIMARY KEY,
  name            TEXT,
  total_pop       INTEGER,
  median_income   INTEGER,
  median_age      NUMERIC,
  pct_hh_under35k NUMERIC,
  pct_hh_35_75k   NUMERIC,
  pct_hh_75_150k  NUMERIC,
  pct_hh_over150k NUMERIC
);

CREATE TABLE competitors (
  ogc_fid      SERIAL PRIMARY KEY,
  wkb_geometry GEOMETRY(Point, 4326),
  id           CHARACTER VARYING,
  name         CHARACTER VARYING,
  brand        JSON
);
"""

# allowed postgis functions and usage rules, also passed as context to claude
POSTGIS_FUNCTIONS = """
Available PostGIS functions (use only these, no others):
- ST_Within(geom_a geometry, geom_b geometry) -> boolean
- ST_Intersects(geom_a geometry, geom_b geometry) -> boolean
- ST_Distance(geom_a geography, geom_b geography) -> float (meters)
- ST_Buffer(geom geography, radius_meters float) -> geometry
- ST_Area(geom geography) -> float (square meters)
- ST_Intersection(geom_a geometry, geom_b geometry) -> geometry
- ST_Centroid(geom geometry) -> geometry
- ST_AsGeoJSON(geom geometry) -> text

Rules:
- Always cast geometry to geography for distance and area: geom::geography
- Never invent PostGIS function names
- Use ST_Intersects for spatial joins, ST_Within for containment checks
- Always include ST_AsGeoJSON(ct.geom) AS geom_json in the SELECT list when querying census_tracts
- Return only the SQL query, no explanation, no markdown fences
"""

# system prompt as a list so the schema block can be cached across calls
SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": (
            "You are a PostGIS SQL expert. Generate a single read-only SQL query.\n\n"
            f"Schema:\n{SCHEMA}\n{POSTGIS_FUNCTIONS}"
        ),
        "cache_control": {"type": "ephemeral"},
    }
]


# fetch actual name values from lookup tables so claude can match user language to real data
def _fetch_lookup_context() -> str:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM trade_areas ORDER BY name")
            trade_area_names = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT name FROM sites ORDER BY name")
            site_names = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    lines = []
    if trade_area_names:
        lines.append(f"trade_areas.name values: {trade_area_names}")
    if site_names:
        lines.append(f"sites.name values: {site_names}")
    return "\n".join(lines)


# send natural-language query to claude and return the generated sql string
def nl_to_spatial_sql(user_query: str) -> str:
    lookup_context = _fetch_lookup_context()
    augmented_query = (
        f"{user_query}\n\nActual name values in the database:\n{lookup_context}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": augmented_query}],
    )
    return response.content[0].text.strip()


# run a sql string against postgres and return rows as a list of dicts
def execute_query(sql: str) -> list[dict]:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


EXAMPLE_QUERY = (
    "Show me census tracts within a 10-minute drive of Woodcroft Shopping Center "
    "in Durham, NC where median income is above $50k and there's no competing "
    "coffee shop within 2 miles."
)

# demo: translate an example query, print the sql, then print results without geom
if __name__ == "__main__":
    sql = nl_to_spatial_sql(EXAMPLE_QUERY)
    print("Generated SQL:\n", sql, "\n")
    for row in execute_query(sql):
        print({k: v for k, v in row.items() if k != "geom_json"})
