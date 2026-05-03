# Spatial Query Tool

Ask questions about a PostGIS trade area database in plain English. The app translates your question to SQL using Claude, runs it, and shows you both the query and a map of the results.

This is a simplified demo companion to the [PostGIS trade area analysis post](https://www.valerieparhamthompson.com/posts/postgis-trade-area-census-isochrones/).

---

## What it does

Type a question like:

> Show me census tracts within a 10-minute drive of Woodcroft Shopping Center in Durham, NC where median income is above $50k and there's no competing coffee shop within 2 miles.

The app:

1. Sends your question to Claude with a system prompt that knows the database schema
2. Gets and displays a PostGIS SQL query
3. Executes the query against your local PostgreSQL database
4. Displays the results as a table and as census tract polygons on an interactive map, colored by median income

---

## Prerequisites

- Python 3.10+
- PostgreSQL running locally with PostGIS enabled
- The `trade_area_db` database populated (see the [April post](https://www.valerieparhamthompson.com/posts/postgis-trade-area-census-isochrones/) for setup)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
```

Open `.env` and fill in your API key:

```
ANTHROPIC_API_KEY=sk-ant-...
DB_DSN=host=localhost dbname=trade_area_db
```

If your PostgreSQL setup requires a username or password, add them to `DB_DSN`:

```
DB_DSN=host=localhost dbname=trade_area_db user=yourname password=yourpass
```

---

## Running the app

```bash
streamlit run app.py
```

The app opens at [http://localhost:8501](http://localhost:8501).

---

## Running from the terminal (no UI)

`spatial_query.py` can also be run directly to print the generated SQL and results:

```bash
python spatial_query.py
```

This is useful for testing the SQL output before the full UI is involved.

---

## Running the eval harness

`eval.py` runs a set of test cases against the SQL generation pipeline. Each case sends a natural language question to Claude and checks that the resulting SQL references the expected tables and PostGIS functions, then executes it against the database and verifies it returns results.

```bash
python eval.py
```

This is useful when you change the system prompt, swap models, or add new schema — run the evals first to confirm the existing queries still work. The script exits with code 1 if any case fails.

---

## What's in the database

| Table           | Contents                                                                               |
| --------------- | -------------------------------------------------------------------------------------- |
| `census_tracts` | Durham County census tract boundaries from TIGER/Line                                  |
| `acs_data`      | ACS 5-year demographic estimates joined by GEOID                                       |
| `trade_areas`   | Drive-time isochrones, including the 10-minute isochrone for Woodcroft Shopping Center |
| `competitors`   | Coffee shop locations from Overture Maps (pre-filtered)                                |
| `sites`         | The Woodcroft Shopping Center site point                                               |

---

## Example questions to try

- Show me census tracts within a 10-minute drive of Woodcroft Shopping Center in Durham, NC where median income is above $50k and there's no competing coffee shop within 2 miles.
- Show me census tracts within the 5-minute drive area where more than 40% of households earn over $50k.
- Which census tracts in the trade area have the highest share of households under $35k?
- What is the total population of census tracts that intersect the trade area?

---

## Files

```
spatial_query.py   Core logic: schema, system prompt, Claude API call, database query
app.py             Streamlit frontend: UI, table display, map rendering
eval.py            Eval harness: test cases for SQL generation quality
requirements.txt   Python dependencies
.env.example       Template for environment variables
```
