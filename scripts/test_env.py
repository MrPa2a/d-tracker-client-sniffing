import sys
import os

print("Python executable:", sys.executable)
print("Path:", sys.path)

try:
    import pydofus
    print("pydofus imported successfully")
except ImportError:
    print("pydofus NOT found")

try:
    from core.d2o_reader import D2OReader
    print("core.d2o_reader imported successfully")
except ImportError as e:
    print(f"core.d2o_reader import failed: {e}")

try:
    import psycopg2
    print("psycopg2 imported successfully")
except ImportError:
    print("psycopg2 NOT found")
