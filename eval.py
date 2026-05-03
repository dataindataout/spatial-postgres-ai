import sys
from dataclasses import dataclass, field

from spatial_query import execute_query, nl_to_spatial_sql


@dataclass
class EvalCase:
    question: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    # minimum rows expected from DB execution; -1 skips execution
    min_rows: int = 1


CASES = [
    EvalCase(
        question=(
            "Show me census tracts within a 10-minute drive of Woodcroft Shopping Center "
            "in Durham, NC where median income is above $50k and there's no competing "
            "coffee shop within 2 miles."
        ),
        must_contain=[
            "ST_AsGeoJSON",
            "census_tracts",
            "acs_data",
            "competitors",
        ],
        must_not_contain=["ST_DWithin", "ST_Overlaps"],
        min_rows=1,
    ),
    EvalCase(
        question=(
            "Show me census tracts within the 5-minute drive area where more than 40% "
            "of households earn over $50k."
        ),
        must_contain=["ST_AsGeoJSON", "census_tracts", "acs_data"],
        must_not_contain=["ST_DWithin"],
        min_rows=1,
    ),
    EvalCase(
        question=(
            "Which census tracts in the trade area have the highest share of "
            "households under $35k?"
        ),
        must_contain=["ST_AsGeoJSON", "census_tracts", "acs_data", "pct_hh_under35k"],
        must_not_contain=["ST_DWithin"],
        min_rows=1,
    ),
    EvalCase(
        question="What is the total population of census tracts that intersect the trade area?",
        must_contain=["census_tracts", "acs_data", "total_pop"],
        min_rows=1,
    ),
    EvalCase(
        question="Show me all sites.",
        must_contain=["sites"],
        min_rows=1,
    ),
]


def run_eval(case: EvalCase) -> dict:
    checks = []
    overall_passed = True
    sql = None
    error = None

    try:
        sql = nl_to_spatial_sql(case.question)
    except Exception as e:
        return {
            "question": case.question,
            "sql": None,
            "checks": [],
            "overall_passed": False,
            "error": f"nl_to_spatial_sql failed: {e}",
        }

    sql_lower = sql.lower()

    for term in case.must_contain:
        passed = term.lower() in sql_lower
        checks.append({"name": f"contains {term}", "passed": passed})
        if not passed:
            overall_passed = False

    for term in case.must_not_contain:
        passed = term.lower() not in sql_lower
        checks.append({"name": f"does not contain {term}", "passed": passed})
        if not passed:
            overall_passed = False

    if case.min_rows >= 0:
        try:
            rows = execute_query(sql)
            passed = len(rows) >= case.min_rows
            checks.append(
                {
                    "name": f">= {case.min_rows} row(s) returned (got {len(rows)})",
                    "passed": passed,
                }
            )
            if not passed:
                overall_passed = False
        except Exception as e:
            checks.append({"name": "executes without error", "passed": False})
            overall_passed = False
            error = str(e)

    return {
        "question": case.question,
        "sql": sql,
        "checks": checks,
        "overall_passed": overall_passed,
        "error": error,
    }


def main():
    passed_count = 0

    for case in CASES:
        result = run_eval(case)
        label = "[PASS]" if result["overall_passed"] else "[FAIL]"
        short_q = (
            case.question[:72] + "..." if len(case.question) > 72 else case.question
        )
        print(f"\n{label} {short_q}")
        for check in result["checks"]:
            icon = "✓" if check["passed"] else "✗"
            print(f"  {icon} {check['name']}")
        if result["error"]:
            print(f"  ! error: {result['error']}")
        if result["sql"] and not result["overall_passed"]:
            print(f"  generated SQL:\n{result['sql']}")
        if result["overall_passed"]:
            passed_count += 1

    total = len(CASES)
    print(f"\n{passed_count}/{total} cases passed.")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
