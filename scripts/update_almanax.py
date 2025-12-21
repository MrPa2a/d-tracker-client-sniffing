import os
import sys
import requests
import re
import datetime
import time
import psycopg2
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

def get_or_create_item(conn, ankama_id, item_data):
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT id FROM items WHERE ankama_id = %s", (ankama_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Create
    name = item_data['name']['fr']
    level = item_data.get('level', 1)
    icon_id = item_data.get('iconId')
    icon_url = f"https://api.dofusdb.fr/img/items/{icon_id}.png" if icon_id else None
    
    # We need a category. For now, let's try to find one or default to something.
    # Or just insert without category if nullable? category_id is nullable in schema?
    # Checking schema: category_id INTEGER REFERENCES public.categories(id)
    # It is nullable.
    
    print(f"Creating item {name} (ID: {ankama_id})...")
    cursor.execute("""
        INSERT INTO items (name, ankama_id, level, icon_url, is_manually_added)
        VALUES (%s, %s, %s, %s, TRUE)
        RETURNING id
    """, (name, ankama_id, level, icon_url))
    
    new_id = cursor.fetchone()[0]
    conn.commit()
    return new_id

def fetch_almanax_day(date_str):
    url = f"https://www.krosmoz.com/en/almanax/{date_str}"
    print(f"Fetching {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_almanax_page(html):
    # Find the offering image to get ID
    # <img src="https://static.ankama.com/dofus/www/game/items/200/40658.w75h75.png" ...>
    # Regex for image
    img_match = re.search(r'static\.ankama\.com/dofus/www/game/items/\d+/(\d+)\.w75h75\.png', html)
    if not img_match:
        print("Could not find offering image.")
        return None, None, None
    
    icon_id = int(img_match.group(1))
    
    # Find quantity and name
    # <p class="f_r">Find 1 Ebonite and take the offering to Antyklime Ax</p>
    # Or similar structure.
    # "Find (\d+) (.+) and take"
    
    text_match = re.search(r'Find (\d+) (.+) and take the offering', html)
    quantity = 1
    if text_match:
        quantity = int(text_match.group(1))
        # name = text_match.group(2) # We don't rely on name from Krosmoz as it is English
    
    # Bonus description
    # <div class="more"> ... </div>
    # This is harder to parse reliably with regex.
    # Let's try to find "Bonus:"
    bonus = "Bonus"
    bonus_match = re.search(r'<h4>DOFUS bonuses and quests</h4>\s*<div class="more">\s*<p>(.+?)</p>', html, re.DOTALL)
    if bonus_match:
        bonus = bonus_match.group(1).strip()
        # Clean up HTML tags if any
        bonus = re.sub(r'<[^>]+>', '', bonus).strip()
        # Remove newlines
        bonus = bonus.replace('\n', ' ')
        
    return icon_id, quantity, bonus

def resolve_item_from_dofusdb(icon_id):
    url = f"https://api.dofusdb.fr/items?iconId={icon_id}&$limit=10"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()['data']
        
        if not data:
            return None
            
        # Filter for resources/consumables/equipment (exclude quest items if possible)
        # SuperType 14 is Quest Item.
        # We want to avoid SuperType 14 unless it's the only option.
        
        candidates = []
        for item in data:
            super_type = item.get('type', {}).get('superTypeId')
            if super_type != 14: # Not a quest item
                candidates.append(item)
        
        if candidates:
            return candidates[0] # Return first non-quest item
        
        return data[0] # Fallback to first item
        
    except Exception as e:
        print(f"Error fetching DofusDB for icon {icon_id}: {e}")
        return None

def main():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.date.today()
    # Scrape next 90 days
    for i in range(90):
        date = today + datetime.timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        print(f"Processing {date_str}...")
        
        # Check if already exists
        cursor.execute("SELECT 1 FROM almanax_calendar WHERE date = %s", (date,))
        if cursor.fetchone():
            print(f"  Already exists. Skipping.")
            continue
            
        html = fetch_almanax_day(date_str)
        if not html:
            continue
            
        icon_id, quantity, bonus = parse_almanax_page(html)
        if not icon_id:
            print("  Failed to parse.")
            continue
            
        print(f"  Found Icon ID: {icon_id}, Quantity: {quantity}")
        
        item_data = resolve_item_from_dofusdb(icon_id)
        if not item_data:
            print(f"  Could not resolve item for icon {icon_id}")
            continue
            
        ankama_id = item_data['id']
        item_name = item_data['name']['fr']
        print(f"  Resolved to: {item_name} (ID: {ankama_id})")
        
        item_id = get_or_create_item(conn, ankama_id, item_data)
        
        cursor.execute("""
            INSERT INTO almanax_calendar (date, item_id, quantity, bonus_description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                quantity = EXCLUDED.quantity,
                bonus_description = EXCLUDED.bonus_description,
                updated_at = NOW()
        """, (date, item_id, quantity, bonus))
        
        conn.commit()
        
        # Be nice to the server
        time.sleep(1)

    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
