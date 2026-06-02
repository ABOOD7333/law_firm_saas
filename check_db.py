import sqlite3
conn = sqlite3.connect('law_firm.db')
cursor = conn.cursor()

# عرض كل الجداول
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('الجداول:', [t[0] for t in tables])

# عرض جميع المكاتب
print('\n=== المكاتب ===')
cursor.execute('SELECT * FROM law_offices')
offices = cursor.fetchall()
cols = [desc[0] for desc in cursor.description]
print('الاعمدة:', cols)
for o in offices:
    print(' ', o)

print('\n=== المستخدمون ===')
cursor.execute('SELECT id, username, name, role, office_id, is_active FROM access_profiles')
users = cursor.fetchall()
for u in users:
    print(' ', u)

conn.close()
