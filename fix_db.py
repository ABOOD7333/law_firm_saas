import psycopg2

conn = psycopg2.connect('postgresql://postgres:CpgDcHxPvpbGJtHOcfFGvQjjivCvJGYc@viaduct.proxy.rlwy.net:38311/railway')
cur = conn.cursor()

# List all tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [r[0] for r in cur.fetchall()]
print('=== TABLES IN RAILWAY DB ===')
for t in tables:
    print(' -', t)

print('\n=== CHECKING payment_requests ===')
if 'payment_requests' in tables:
    print('payment_requests table EXISTS!')
else:
    print('payment_requests table MISSING - This is likely the problem!')
    print('\nCreating it now...')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_requests (
            id SERIAL PRIMARY KEY,
            office_id INTEGER NOT NULL REFERENCES law_offices(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES access_profiles(id) ON DELETE SET NULL,
            plan TEXT NOT NULL,
            amount REAL,
            currency TEXT DEFAULT 'USD',
            transfer_ref TEXT,
            receipt_base64 TEXT,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewed_by INTEGER
        )
    """)
    conn.commit()
    print('Table created successfully!')

conn.close()
