from ahvn.cache import JsonCache
from ahvn.utils import hpj


if __name__ == "__main__":
    PATH = "./"
    FUNC = "gen_field_synonyms"
    cache = JsonCache(path=PATH)

    exps = [
        {
            "inputs": {
                "name": "period",
                "short_description": "Accounting period",
                "description": "This column represents the accounting period, formatted as YYYYMM, e.g., '202401'. Use this for time-based filtering or aggregation.",
                "max_count": 3,
            },
            "expected": ["fiscal_period", "time_period", "month_period"],
        },
        {
            "inputs": {
                "name": "ytd_value",
                "short_description": "Year-to-date cumulative value",
                "description": "Indicates the cumulative sales value for the current year from the beginning to the current period.",
                "max_count": 2,
            },
            "expected": ["ytd", "cumulative_yearly"],
        },
        {
            "inputs": {
                "name": "region",
                "short_description": "Sales region",
                "description": "Stores geographical sales regions, with possible values like 'East China', 'South China', 'Central China', and 'North China'.",
                "max_count": 3,
            },
            "expected": ["area", "district", "territory"],
        },
        {
            "inputs": {
                "name": "state_province",
                "short_description": "State or province",
                "description": "Specifies the state or province of the sales, with possible values like 'California', 'New York', 'Texas', etc.",
                "max_count": 2,
            },
            "expected": ["province", "state"],
        },
        {
            "inputs": {
                "name": "brand",
                "short_description": "Brand name",
                "description": "Indicates the automotive brand, with possible values like 'Toyota', 'Honda', 'Ford', etc.",
                "max_count": 3,
            },
            "expected": ["manufacturer", "make", "brand_name"],
        },
    ]

    for exp in exps:
        cache.set(func=FUNC, inputs=exp["inputs"], output=exp["expected"], expected=exp["expected"])
