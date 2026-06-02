import psycopg2
import sys

sys.stdout.reconfigure(encoding='utf-8')
url = 'postgresql://postgres:CpgDcHxPvpbGJtHOcfFGvQjjivCvJGYc@viaduct.proxy.rlwy.net:38311/railway'
conn = psycopg2.connect(url, connect_timeout=10)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
tables = [row[0] for row in cur.fetchall()]

for table in tables:
    try:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TEXT;')
        cur.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0 NOT NULL;')
        print(f'Added columns to {table}')
    except Exception as e:
        print(f'Error adding to {table}: {e}')

print('Done fixing all tables!')
