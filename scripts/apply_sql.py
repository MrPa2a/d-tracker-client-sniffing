import os
import psycopg2
from dotenv import load_dotenv
import sys

# Load env
load_dotenv()

def apply_sql(file_path):
    db_url = os.getenv('SUPABASE_DB_URL')
    if not db_url:
        # Try to construct from individual fields
        host = os.getenv('DB_HOST')
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        port = os.getenv('DB_PORT', '5432')
        dbname = os.getenv('DB_NAME', 'postgres')
        
        if host and user and password:
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        else:
            print("Error: SUPABASE_DB_URL or DB credentials not found in .env")
            return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print(f"Reading {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql = f.read()
        except UnicodeDecodeError:
            # Fallback to utf-16 if utf-8 fails (PowerShell redirection often creates UTF-16 LE BOM)
            with open(file_path, 'r', encoding='utf-16') as f:
                sql = f.read()
            
        print("Executing SQL...")
        cur.execute(sql)
        conn.commit()
        print("Success!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_sql.py <path_to_sql_file>")
    else:
        apply_sql(sys.argv[1])
