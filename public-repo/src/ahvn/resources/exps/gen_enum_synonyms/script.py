from ahvn.cache import JsonCache
from ahvn.utils import hpj


if __name__ == "__main__":
    PATH = "./"
    FUNC = "gen_enum_synonyms"
    cache = JsonCache(path=PATH)

    exps = [
        {
            "inputs": {
                "name": "state",
                "short_description": "State name, possible values include: California, New York, Texas, Florida, Illinois, Pennsylvania, Ohio",
                "description": "Specifies the state of the sales. Ensure state names match the provided list to avoid query errors.",
                "base_value": "California",
                "max_count": 3,
            },
            "expected": ["CA", "Calif", "Cali"],
        },
        {
            "inputs": {
                "name": "state",
                "short_description": "State name, possible values include: California, New York, Texas, Florida, Illinois, Pennsylvania, Ohio",
                "description": "Specifies the state of the sales. Ensure state names match the provided list to avoid query errors.",
                "base_value": "New York",
                "max_count": 3,
            },
            "expected": ["NY", "N.Y.", "New York State"],
        },
        {
            "inputs": {
                "name": "region",
                "short_description": "Regional division, possible values include: Northeast, Southeast, Midwest, Southwest, West",
                "description": "Stores geographical sales regions with predefined regional divisions.",
                "base_value": "Northeast",
                "max_count": 2,
            },
            "expected": ["NE", "Northeastern"],
        },
        {
            "inputs": {
                "name": "brand",
                "short_description": "Brand name, possible values include: Toyota, Honda, Ford, Chevrolet",
                "description": "Indicates the automotive brand with a limited set of manufacturer names.",
                "base_value": "Toyota",
                "max_count": 3,
            },
            "expected": ["TOYOTA", "Toyota Motor"],
        },
        {
            "inputs": {
                "name": "city",
                "short_description": "City name, possible values include: Los Angeles, San Francisco, New York City, Chicago, Houston",
                "description": "This column represents the city where sales occurred, with a list of possible values including major US cities.",
                "base_value": "Los Angeles",
                "max_count": 2,
            },
            "expected": ["LA", "L.A."],
        },
    ]

    for exp in exps:
        cache.set(func=FUNC, inputs=exp["inputs"], output=exp["expected"], expected=exp["expected"])
