import os
import sys
import psycopg2
import requests
import time
import re
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

def get_db_connection():
    try:
        conn = psycopg2.connect(**get_db_config())
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def fetch_effect_definitions():
    print("Fetching effect definitions from DofusDB...")
    base_url = "https://api.dofusdb.fr/effects"
    limit = 50
    skip = 0
    effects_map = {}
    
    while True:
        url = f"{base_url}?$limit={limit}&$skip={skip}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                items = data.get('data', [])
                if not items:
                    break
                
                for effect in items:
                    desc = effect.get('description', {}).get('fr', '')
                    if desc:
                        effects_map[effect['id']] = desc
                
                skip += limit
            else:
                print(f"Failed to fetch effects: {response.status_code}")
                break
        except Exception as e:
            print(f"Error fetching effects: {e}")
            break
            
    # Manual overrides for missing descriptions (Unity/New effects)
    manual_overrides = {
        2800: "#1% Dommages mêlée",
        2801: "#1% Dommages mêlée",
        2802: "#1% Résistance mêlée",
        2803: "#1% Résistance mêlée",
        2804: "#1% Dommages distance",
        2805: "#1% Dommages distance",
        2806: "#1% Résistance distance",
        2807: "#1% Résistance distance",
        2808: "#1% Dommages d'armes",
        2809: "#1% Dommages d'armes",
        2812: "#1% Dommages aux sorts",
        2813: "#1% Dommages aux sorts"
    }
    effects_map.update(manual_overrides)

    print(f"Loaded {len(effects_map)} effect definitions.")
    return effects_map

def format_description(pattern, min_val, max_val):
    if not pattern:
        return f"Effect {min_val}" + (f" à {max_val}" if min_val != max_val else "")

    text = pattern

    if min_val == max_val:
        # Heuristic: If it's a range pattern (contains {{~1~2), remove the range part and #2
        if "{{~1~2" in text:
             text = re.sub(r'\{\{~1~2.*?\}\}', '', text)
             text = text.replace('#2', '')
        
        text = text.replace('#1', str(min_val))
        # Just in case #2 is still there (if not a range pattern)
        text = text.replace('#2', str(max_val))
    else:
        # Range case
        # Replace conditional {{~1~2 content }} with content
        text = re.sub(r'\{\{~1~2(.*?)\}\}', r'\1', text)
        text = text.replace('#1', str(min_val)).replace('#2', str(max_val))

    # Handle pluralization {{~ps}} -> s if max_val > 1
    # We treat max_val as the deciding factor for the whole string pluralization
    def replace_plural(match):
        return 's' if max_val > 1 else ''

    text = re.sub(r'\{\{~ps\}\}', replace_plural, text)
    
    # Strip remaining tags (including {{~zs}} which we don't handle specifically yet)
    text = re.sub(r'\{\{.*?\}\}', '', text) 
    
    # Fix double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def ingest_effects():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 0. Load Effect Definitions
    effects_map = fetch_effect_definitions()

    # 1. Get all existing Ankama IDs from our DB to filter
    print("Fetching existing items from DB...")
    cursor.execute("SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL")
    # Map ankama_id -> db_id
    existing_items = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"Found {len(existing_items)} items in local DB.")

    # 2. Iterate DofusDB API
    base_url = "https://api.dofusdb.fr/items"
    limit = 50
    skip = 0
    total_processed = 0
    total_updated = 0

    print("Starting ingestion from DofusDB...")

    while True:
        try:
            url = f"{base_url}?$limit={limit}&$skip={skip}&$select[]=id&$select[]=effects"
            # We only need id and effects fields to save bandwidth
            # Note: DofusDB uses $limit, $skip, $select syntax usually
            
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error fetching DofusDB: {response.status_code}")
                time.sleep(5)
                continue
            
            data = response.json()
            items_batch = data.get('data', [])
            
            if not items_batch:
                print("No more items found.")
                break

            for item_data in items_batch:
                ankama_id = item_data.get('id')
                
                # Skip if we don't have this item in our DB
                if ankama_id not in existing_items:
                    continue

                db_id = existing_items[ankama_id]
                effects = item_data.get('effects', [])

                if not effects:
                    continue

                # Clear existing effects for this item to avoid duplicates/stale data
                cursor.execute("DELETE FROM item_effects WHERE item_id = %s", (db_id,))

                # Insert new effects
                for i, effect in enumerate(effects):
                    effect_id = effect.get('effectId')
                    from_val = effect.get('from', 0)
                    to_val = effect.get('to', 0)
                    
                    # Logic: if to_val is 0, it's a fixed value (min=max=from)
                    # Unless it's a range 0-0 which is useless, but usually 0 means "not set" or "same as from" in this context for fixed stats
                    # For safety:
                    min_val = from_val
                    max_val = to_val if to_val != 0 else from_val
                    
                    # Handle edge case where from > to (sometimes happens in bad data, swap them)
                    if min_val > max_val:
                        min_val, max_val = max_val, min_val

                    # Format Description
                    pattern = effects_map.get(effect_id)
                    if pattern:
                        description = format_description(pattern, min_val, max_val)
                    else:
                        description = f"Effect {effect_id}: {min_val}"
                        if min_val != max_val:
                            description += f" à {max_val}"

                    cursor.execute("""
                        INSERT INTO item_effects (item_id, effect_id, min_value, max_value, formatted_description, order_index)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (db_id, effect_id, min_val, max_val, description, i))
                
                total_updated += 1

            conn.commit()
            total_processed += len(items_batch)
            print(f"Processed {total_processed} items... (Updated: {total_updated})")
            
            skip += limit
            time.sleep(0.2) # Be nice to the API

        except Exception as e:
            print(f"Error during processing: {e}")
            time.sleep(5)

    cursor.close()
    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_effects()
