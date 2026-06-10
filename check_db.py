import psycopg2

conn = psycopg2.connect('postgresql://postgres:CpgDcHxPvpbGJtHOcfFGvQjjivCvJGYc@viaduct.proxy.rlwy.net:38311/railway')
cur = conn.cursor()

# Check the ABOOD user
cur.execute("SELECT id, username, email, role, is_active, failed_attempts, office_id FROM access_profiles WHERE username='ABOOD' OR email='ABOOD'")
rows = cur.fetchall()
print('=== ABOOD USER ===')
for r in rows:
    print(f'  id={r[0]}, username={r[1]}, email={r[2]}, role={r[3]}, active={r[4]}, fails={r[5]}, office={r[6]}')

# Check offices
cur.execute("SELECT id, name, is_active, subscription_plan FROM law_offices LIMIT 5")
rows = cur.fetchall()
print('\n=== OFFICES ===')
for r in rows:
    print(f'  id={r[0]}, name={r[1]}, active={r[2]}, plan={r[3]}')

conn.close()
