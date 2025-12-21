import requests
import json

def get_item_effects(item_id):
    url = f"https://api.dofusdb.fr/items/{item_id}"
    try:
        response = requests.get(url)
        data = response.json()
        print(json.dumps(data.get('effects', []), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_item_effects(19252)
