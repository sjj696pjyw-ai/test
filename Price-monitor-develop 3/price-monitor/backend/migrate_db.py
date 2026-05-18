"""
Migration script to remove catalog_url column from competitors table
and ensure domain column exists.
"""
import sqlite3
import os

# Get the database path from the config or use default
DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///pricemonitor.db').replace('sqlite:///', '')

if not DB_PATH:
    DB_PATH = 'pricemonitor.db'

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if the table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='competitors'")
if not cursor.fetchone():
    print("Table 'competitors' does not exist. No migration needed.")
    conn.close()
    exit(0)

# Get current columns
cursor.execute("PRAGMA table_info(competitors)")
columns = [col[1] for col in cursor.fetchall()]
print(f"Current columns: {columns}")

if 'catalog_url' not in columns:
    print("Column 'catalog_url' does not exist. No migration needed.")
    conn.close()
    exit(0)

if 'domain' not in columns:
    print("ERROR: Column 'domain' does not exist. Cannot migrate.")
    conn.close()
    exit(1)

# SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
# Get all data except catalog_url
new_columns = [col for col in columns if col != 'catalog_url']
columns_str = ', '.join([f'"{col}"' for col in new_columns])

# Create temporary table
cursor.execute(f'''
    CREATE TABLE competitors_temp AS 
    SELECT {columns_str} FROM competitors
''')

# Drop old table
cursor.execute('DROP TABLE competitors')

# Rename temporary table
cursor.execute('ALTER TABLE competitors_temp RENAME TO competitors')

conn.commit()
print(f"Successfully removed 'catalog_url' column from 'competitors' table.")
print(f"New columns: {new_columns}")

conn.close()
