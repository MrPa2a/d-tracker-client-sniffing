
import os
import sys
import time
import psycopg2
import requests
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

def get_or_create_item_from_dofusdb(cursor, ankama_id):
    # 1. Check DB by GID
    cursor.execute("SELECT id FROM items WHERE ankama_id = %s", (ankama_id,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # 2. Fetch from DofusDB
    # print(f"Fetching item info for GID {ankama_id} from DofusDB...")
    try:
        resp = requests.get(f"https://api.dofusdb.fr/items?id={ankama_id}")
        if resp.status_code != 200:
            print(f"Failed to fetch item {ankama_id} (Status: {resp.status_code})")
            return None
        data = resp.json()
        if data['total'] == 0:
            print(f"Item {ankama_id} not found on DofusDB")
            return None
        
        item_data = data['data'][0]
        name = item_data['name']['fr']
        icon_id = item_data.get('iconId')
        icon_url = f"https://api.dofusdb.fr/img/items/{icon_id}.png" if icon_id else None
        
        # 3. Check DB by Name (to avoid duplicates if GID was missing)
        cursor.execute("SELECT id, ankama_id FROM items WHERE name = %s", (name,))
        existing = cursor.fetchone()
        
        if existing:
            existing_id, existing_gid = existing
            if existing_gid is None:
                # Update GID
                cursor.execute("UPDATE items SET ankama_id = %s, icon_url = %s, updated_at = NOW() WHERE id = %s", (ankama_id, icon_url, existing_id))
                return existing_id
            elif existing_gid == ankama_id:
                return existing_id
            else:
                print(f"Warning: Name collision for '{name}'. Existing GID: {existing_gid}, New GID: {ankama_id}. Creating new entry.")
                # Proceed to insert (assuming name is not unique constraint or we handle it)
                # If name is unique, we can't insert.
                # Let's check schema. Usually name is unique or we rely on it.
                # If name is unique, we are stuck.
                # But let's try to insert and see.
        
        # 4. Insert
        cursor.execute("""
            INSERT INTO items (name, ankama_id, icon_url, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (name) DO NOTHING
            RETURNING id
        """, (name, ankama_id, icon_url))
        
        row = cursor.fetchone()
        if row:
            new_id = row[0]
            print(f"Created item '{name}' (ID: {new_id}, GID: {ankama_id})")
            return new_id
        else:
            # Conflict happened and DO NOTHING executed.
            # This means name exists. We already handled it above?
            # Maybe race condition or I missed something.
            cursor.execute("SELECT id FROM items WHERE name = %s", (name,))
            return cursor.fetchone()[0]

    except Exception as e:
        print(f"Error creating item {ankama_id}: {e}")
        return None

def update_recipes():
    print("--- Starting Recipe Update from DofusDB ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all recipes that are not locked
    cursor.execute("""
        SELECT r.id, r.result_item_id, i.ankama_id, i.name
        FROM recipes r
        JOIN items i ON r.result_item_id = i.id
        WHERE r.is_locked = FALSE
    """)
    recipes = cursor.fetchall()
    total_recipes = len(recipes)
    print(f"Found {total_recipes} recipes to check.")
    
    updated_count = 0
    processed_count = 0
    
    for r_id, result_item_id, result_gid, result_name in recipes:
        processed_count += 1
        if processed_count % 50 == 0:
            print(f"Processed {processed_count}/{total_recipes} recipes... (Updated: {updated_count})")
            
        if not result_gid:
            # print(f"Skipping recipe {r_id} (Item {result_name} has no GID)")
            continue
            
        try:
            # Fetch recipe from DofusDB
            resp = requests.get(f"https://api.dofusdb.fr/recipes?resultId={result_gid}")
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data['total'] == 0:
                # print(f"No recipe on DofusDB for {result_name}")
                continue
                
            dofus_recipe = data['data'][0]
            new_ingredients = [] # List of (db_id, qty)
            
            ing_ids = dofus_recipe['ingredientIds']
            quantities = dofus_recipe['quantities']
            
            valid_recipe = True
            for i, ing_gid in enumerate(ing_ids):
                qty = quantities[i]
                ing_db_id = get_or_create_item_from_dofusdb(cursor, ing_gid)
                if not ing_db_id:
                    print(f"Could not resolve ingredient {ing_gid} for recipe {result_name}")
                    valid_recipe = False
                    break
                new_ingredients.append((ing_db_id, qty))
            
            if not valid_recipe:
                continue
                
            # Compare with existing
            cursor.execute("SELECT item_id, quantity FROM recipe_ingredients WHERE recipe_id = %s", (r_id,))
            current_ingredients = set(cursor.fetchall())
            new_ingredients_set = set(new_ingredients)
            
            if current_ingredients != new_ingredients_set:
                print(f"Updating recipe for {result_name} ({result_gid})...")
                # Update
                cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", (r_id,))
                for item_id, qty in new_ingredients:
                    cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_id, quantity) VALUES (%s, %s, %s)", (r_id, item_id, qty))
                updated_count += 1
                conn.commit() 
                
        except Exception as e:
            print(f"Error processing {result_name}: {e}")
            conn.rollback()
            
        # Rate limiting
        # time.sleep(0.01) 
        
    print(f"Finished. Updated {updated_count} recipes out of {total_recipes}.")
    conn.close()

if __name__ == "__main__":
    update_recipes()
