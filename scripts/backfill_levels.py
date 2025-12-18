import os
import sys
import psycopg2
import requests
import time
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

def backfill_levels():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Apply Schema Change
    print("Applying schema migration (adding level column)...")
    try:
        cursor.execute("ALTER TABLE public.items ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_level ON public.items(level);")
        conn.commit()
        print("Schema updated.")
    except Exception as e:
        print(f"Error updating schema: {e}")
        conn.rollback()
        return

    # 2. Get all existing Ankama IDs
    print("Fetching existing items from DB...")
    cursor.execute("SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL")
    existing_items = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"Found {len(existing_items)} items in local DB.")

    # 3. Iterate DofusDB API
    base_url = "https://api.dofusdb.fr/items"
    limit = 50
    skip = 0
    total_updated = 0

    print("Starting level backfill from DofusDB...")

    while True:
        try:
            # Fetch id and level
            url = f"{base_url}?$limit={limit}&$skip={skip}&$select[]=id&$select[]=level"
            
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

            updates = []
            for item_data in items_batch:
                ankama_id = item_data.get('id')
                level = item_data.get('level')
                
                if ankama_id in existing_items and level is not None:
                    db_id = existing_items[ankama_id]
                    updates.append((level, db_id))

            if updates:
                # Batch update
                cursor.executemany("UPDATE items SET level = %s WHERE id = %s", updates)
                conn.commit()
                total_updated += len(updates)
                print(f"Updated {len(updates)} items (Total: {total_updated})")

            skip += limit
            time.sleep(0.1) # Rate limiting

        except Exception as e:
            print(f"Error in loop: {e}")
            time.sleep(5)

    cursor.close()
    conn.close()
    print("Backfill complete.")

if __name__ == "__main__":
    backfill_levels()
