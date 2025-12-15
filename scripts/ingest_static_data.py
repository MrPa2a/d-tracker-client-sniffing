import os
import sys
import psycopg2
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path to allow importing core if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pydofus.d2o import D2OReader
    from pydofus.d2i import D2I
except ImportError:
    print("Error: PyDofus library not found.")
    print("Please install PyDofus (e.g. from https://github.com/balciseri/PyDofus) or ensure it is in your PYTHONPATH.")
    print("If you are using the project's venv, make sure PyDofus is installed there.")

# Database Configuration
def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

PATHS = {
    "dofus_data": os.path.join(os.path.dirname(__file__), "../dofus_data"),
    "common": os.path.join(os.path.dirname(__file__), "../dofus_data/common"),
    "i18n": os.path.join(os.path.dirname(__file__), "../dofus_data/i18n")
}

def get_db_connection(dry_run=False):
    if dry_run:
        print("[DRY-RUN] Skipping DB connection.")
        return None
    try:
        conn = psycopg2.connect(**get_db_config())
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def load_i18n():
    i18n_path = os.path.join(PATHS["i18n"], "i18n_fr.d2i")
    if not os.path.exists(i18n_path):
        print(f"Error: i18n file not found at {i18n_path}")
        return None
    
    reader = D2I(open(i18n_path, "rb"))
    data = reader.read()
    return data["texts"]

def sync_jobs(conn, i18n_texts, dry_run=False):
    print("--- Syncing Jobs ---")
    jobs_path = os.path.join(PATHS["common"], "Jobs.d2o")
    if not os.path.exists(jobs_path):
        print(f"Error: Jobs.d2o not found at {jobs_path}")
        return

    reader = D2OReader(open(jobs_path, "rb"))
    jobs = reader.get_objects()
    
    if dry_run:
        print(f"[DRY-RUN] Found {len(jobs)} jobs to sync.")
        if len(jobs) > 0:
            print(f"[DRY-RUN] Sample Job: {jobs[0]}")
        return

    cursor = conn.cursor()
    count = 0
    
    for job in jobs:
        job_id = job['id']
        name_id = job.get('nameId')
        icon_id = job.get('iconId')
        
        name = i18n_texts.get(name_id) if name_id else f"Job {job_id}"
        
        # Upsert Job
        cursor.execute("""
            INSERT INTO jobs (id, name, icon_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                icon_id = EXCLUDED.icon_id;
        """, (job_id, name, icon_id))
        count += 1
        
    conn.commit()
    cursor.close()
    print(f"Synced {count} jobs.")

def sync_recipes(conn, i18n_texts, dry_run=False):
    print("--- Syncing Recipes ---")
    recipes_path = os.path.join(PATHS["common"], "Recipes.d2o")
    items_path = os.path.join(PATHS["common"], "Items.d2o")
    
    if not os.path.exists(recipes_path):
        print(f"Error: Recipes.d2o not found at {recipes_path}")
        return

    # Load Items D2O for fallback info
    print("Loading Items.d2o...")
    items_reader = D2OReader(open(items_path, "rb"))
    items_dict = {item['id']: item for item in items_reader.get_objects()}
    
    print("Loading Recipes.d2o...")
    recipes_reader = D2OReader(open(recipes_path, "rb"))
    recipes = recipes_reader.get_objects()
    
    if dry_run:
        print(f"[DRY-RUN] Found {len(recipes)} recipes to sync.")
        return

    cursor = conn.cursor()
    
    # 1. Load mappings to resolve Ankama ID -> DB ID
    print("Loading existing items from DB...")
    # We need to know which DB ID corresponds to which Ankama ID
    cursor.execute("SELECT ankama_id, id FROM items WHERE ankama_id IS NOT NULL")
    ankama_to_db_id = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Also load name -> {id, ankama_id} for fallback
    cursor.execute("SELECT name, id, ankama_id FROM items")
    name_to_item = {row[0]: {'id': row[1], 'ankama_id': row[2]} for row in cursor.fetchall()}
    
    print(f"Loaded {len(ankama_to_db_id)} items with Ankama ID and {len(name_to_item)} items by name.")

    def get_or_create_item(ankama_id):
        # Case A: Already mapped
        if ankama_id in ankama_to_db_id:
            return ankama_to_db_id[ankama_id]
            
        # Case B: Not mapped, need to find or create
        if ankama_id not in items_dict:
            # Item doesn't exist in D2O? Can't create it.
            return None
            
        item_data = items_dict[ankama_id]
        name_id = item_data.get('nameId')
        item_name = i18n_texts.get(name_id)
        
        if not item_name:
            return None
            
        # Case C: Check if exists by name
        if item_name in name_to_item:
            existing = name_to_item[item_name]
            db_id = existing['id']
            existing_ankama_id = existing['ankama_id']
            
            if existing_ankama_id is None:
                # SAFE UPDATE: Only update if currently NULL
                cursor.execute("UPDATE items SET ankama_id = %s WHERE id = %s", (ankama_id, db_id))
                ankama_to_db_id[ankama_id] = db_id
                # Update local cache
                existing['ankama_id'] = ankama_id
                return db_id
            elif existing_ankama_id == ankama_id:
                # Already matches (should have been caught by Case A, but just in case)
                ankama_to_db_id[ankama_id] = db_id
                return db_id
            else:
                # CONFLICT: Name exists but has different ID.
                print(f"Warning: Conflict for '{item_name}'. DB has GID {existing_ankama_id}, D2O wants {ankama_id}. Skipping.")
                return None
            
        # Case D: Create new item
        item_icon = item_data.get('iconId')
        
        cursor.execute("""
            INSERT INTO items (name, ankama_id, icon_url, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (name) DO NOTHING
            RETURNING id;
        """, (item_name, ankama_id, f"https://static.ankama.com/dofus/www/game/items/200/{item_icon}.png"))
        
        row = cursor.fetchone()
        if row:
            new_id = row[0]
            ankama_to_db_id[ankama_id] = new_id
            name_to_item[item_name] = {'id': new_id, 'ankama_id': ankama_id}
            return new_id
        else:
            # Should not happen due to checks above, but concurrency could cause it
            return None

    recipes_count = 0
    ingredients_count = 0
    
    for recipe in recipes:
        result_ankama_id = recipe['resultId']
        ingredient_ankama_ids = recipe['ingredientIds']
        quantities = recipe['quantities']
        job_id = recipe['jobId']
        
        # Resolve Result Item
        result_db_id = get_or_create_item(result_ankama_id)
        if not result_db_id:
            # print(f"Skipping recipe for unknown item {result_ankama_id}")
            continue
            
        # Insert/Update Recipe Header
        cursor.execute("""
            INSERT INTO recipes (result_item_id, job_id, level)
            VALUES (%s, %s, %s)
            ON CONFLICT (result_item_id) DO UPDATE
            SET job_id = EXCLUDED.job_id,
                updated_at = NOW()
            RETURNING id;
        """, (result_db_id, job_id, 1))
        
        recipe_db_id = cursor.fetchone()[0]
        
        # Handle Ingredients
        for i, ing_ankama_id in enumerate(ingredient_ankama_ids):
            qty = quantities[i]
            
            ing_db_id = get_or_create_item(ing_ankama_id)
            if not ing_db_id:
                print(f"Warning: Ingredient {ing_ankama_id} not found/creatable. Skipping ingredient.")
                continue

            # Insert Recipe Ingredient
            cursor.execute("""
                INSERT INTO recipe_ingredients (recipe_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (recipe_id, item_id) DO UPDATE
                SET quantity = EXCLUDED.quantity;
            """, (recipe_db_id, ing_db_id, qty))
            ingredients_count += 1
            
        recipes_count += 1
        if recipes_count % 100 == 0:
            print(f"Processed {recipes_count} recipes...")
            
    conn.commit()
    cursor.close()
    print(f"Sync Complete. Recipes: {recipes_count}, Ingredients: {ingredients_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Dofus static data (Jobs, Recipes) into DB.")
    parser.add_argument("--dry-run", action="store_true", help="Run without connecting to DB to verify parsing.")
    args = parser.parse_args()

    try:
        conn = get_db_connection(dry_run=args.dry_run)
        i18n_texts = load_i18n()
        
        if i18n_texts:
            sync_jobs(conn, i18n_texts, dry_run=args.dry_run)
            sync_recipes(conn, i18n_texts, dry_run=args.dry_run)
            
        if conn:
            conn.close()
    except Exception as e:
        print(f"Fatal Error: {e}")
