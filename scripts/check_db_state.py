import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_config():
    return {
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

def check_tables():
    try:
        conn = psycopg2.connect(**get_db_config())
        cursor = conn.cursor()
        
        tables = ['jobs', 'recipes', 'recipe_ingredients']
        missing = []
        
        print("Checking database structure...")
        for table in tables:
            cursor.execute(f"SELECT to_regclass('public.{table}');")
            if cursor.fetchone()[0] is None:
                missing.append(table)
            else:
                print(f"✅ Table '{table}' exists.")
                
        if missing:
            print(f"\n❌ Missing tables: {', '.join(missing)}")
            print("You need to apply the SQL migration before running the ingestion.")
            return False
        
        print("\n✅ All tables are present. You are ready to go!")
        return True
        
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    check_tables()
