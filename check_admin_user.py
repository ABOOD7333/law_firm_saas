import subprocess

script = """
import os
from sqlalchemy import create_engine, text

db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, name, username, email, role, is_superadmin, is_active, state FROM access_profiles WHERE is_superadmin = 1 OR role LIKE '%مدير%' OR email LIKE '%abood%'"))
    for row in res:
        print(dict(row._mapping))
"""

proc = subprocess.Popen(['ssh', 'root@179.198.198.38', 'docker exec -i lawsaas_app python3'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
stdout, stderr = proc.communicate(input=script)
print("STDOUT:\n", stdout)
print("STDERR:\n", stderr)
