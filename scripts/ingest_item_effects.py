import os
import sys
import psycopg2
import requests
import time
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

def ingest_effects():
    conn = get_db_connection()
    cursor = conn.cursor()

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

                    # Generate a simple description (Placeholder)
                    # We could improve this with a mapping later
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
