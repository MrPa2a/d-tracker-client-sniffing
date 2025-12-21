import requests

def search_effects():
    base_url = "https://api.dofusdb.fr/effects"
    limit = 50
    skip = 0
    
    while True:
        url = f"{base_url}?$limit={limit}&$skip={skip}"
        try:
            response = requests.get(url)
            data = response.json()
            items = data.get('data', [])
            if not items:
                break
            
            for effect in items:
                desc = effect.get('description', {}).get('fr', '')
                eid = effect['id']
                
                if 410 <= eid <= 430:
                    print(f"ID: {eid}, Description: {desc}")

            skip += limit
            if skip > 2000: 
                break
                
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    search_effects()
