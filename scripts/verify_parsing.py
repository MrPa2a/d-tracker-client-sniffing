import sys
import os
import json

# Add project root to path to allow importing pydofus
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pydofus.d2o import D2OReader
    from pydofus.d2i import D2I
except ImportError as e:
    print(f"Error importing pydofus: {e}")
    sys.exit(1)

PATHS = {
    "common": os.path.join(os.path.dirname(__file__), "../dofus_data/common"),
    "i18n": os.path.join(os.path.dirname(__file__), "../dofus_data/i18n")
}

def verify_jobs():
    print("\n--- Verifying Jobs.d2o ---")
    path = os.path.join(PATHS["common"], "Jobs.d2o")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    try:
        with open(path, "rb") as f:
            reader = D2OReader(f)
            jobs = reader.get_objects()
            print(f"Found {len(jobs)} jobs.")
            if len(jobs) > 0:
                print("Sample Job:", json.dumps(jobs[0], indent=2, default=str))
    except Exception as e:
        print(f"Error reading Jobs.d2o: {e}")

def verify_recipes():
    print("\n--- Verifying Recipes.d2o ---")
    path = os.path.join(PATHS["common"], "Recipes.d2o")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    try:
        with open(path, "rb") as f:
            reader = D2OReader(f)
            recipes = reader.get_objects()
            print(f"Found {len(recipes)} recipes.")
            if len(recipes) > 0:
                print("Sample Recipe:", json.dumps(recipes[0], indent=2, default=str))
                
                # Check keys
                keys = recipes[0].keys()
                print("Keys available:", list(keys))
                
                expected_keys = ['resultId', 'ingredientIds', 'quantities', 'jobId']
                missing = [k for k in expected_keys if k not in keys]
                if missing:
                    print(f"WARNING: Missing expected keys: {missing}")
                else:
                    print("Structure looks correct.")
    except Exception as e:
        print(f"Error reading Recipes.d2o: {e}")

if __name__ == "__main__":
    verify_jobs()
    verify_recipes()
