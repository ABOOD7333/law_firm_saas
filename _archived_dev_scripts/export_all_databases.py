import sys, os, json, sqlite3
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

output_lines = []
output_lines.append("=" * 70)
output_lines.append("  تقرير قواعد البيانات الكاملة - LawSaaS")
output_lines.append(f"  التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
output_lines.append("=" * 70)

# ────────────────────────────────────────────────────────────────
# 1) SQLite — law_firm1
# ────────────────────────────────────────────────────────────────
output_lines.append("\n\n" + "━" * 70)
output_lines.append("  [1] SQLite — law_firm.db (مشروع law_firm1)")
output_lines.append("━" * 70)

sqlite_path = r"C:\Users\Roots\Desktop\law_firm1\law_firm.db"
try:
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    output_lines.append(f"\n  عدد الجداول: {len(tables)}")

    for table in tables:
        output_lines.append(f"\n  {'─'*60}")
        output_lines.append(f"  الجدول: {table}")
        output_lines.append(f"  {'─'*60}")

        # Get columns
        cur.execute(f"PRAGMA table_info('{table}')")
        cols = cur.fetchall()
        col_names = [c[1] for c in cols]
        output_lines.append(f"  الأعمدة: {', '.join(col_names)}")

        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM '{table}'")
        count = cur.fetchone()[0]
        output_lines.append(f"  عدد السجلات: {count}")

        # Get first 50 rows
        if count > 0:
            cur.execute(f"SELECT * FROM '{table}' LIMIT 50")
            rows = cur.fetchall()
            output_lines.append(f"\n  البيانات (أول {min(count,50)} سجل):")
            output_lines.append("  " + " | ".join(col_names))
            output_lines.append("  " + "-" * min(80, len(" | ".join(col_names)) + 4))
            for row in rows:
                row_str = " | ".join([str(v)[:30] if v is not None else "NULL" for v in row])
                output_lines.append("  " + row_str)
            if count > 50:
                output_lines.append(f"\n  ... و {count - 50} سجل إضافي")
    conn.close()
except Exception as e:
    output_lines.append(f"  خطأ: {e}")

# ────────────────────────────────────────────────────────────────
# 2) PostgreSQL — جميع القواعد المحلية
# ────────────────────────────────────────────────────────────────
try:
    import psycopg2
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

pg_databases = [
    {"db": "law_firm_pg_test", "project": "law_firm_pg_test"},
    {"db": "law_firms",        "project": "law_firms"},
    {"db": "sems_db",          "project": "Smart Electricity Management System"},
    {"db": "postgres",         "project": "قاعدة النظام الافتراضية"},
]

# Try multiple passwords
passwords_to_try = [
    "sems_secure_pass_2026",
    "ALalimi2004/10/14",
    "postgres",
    "admin",
    "123456",
    "password",
    "root",
]

def try_connect(dbname, passwords):
    for pwd in passwords:
        try:
            conn = psycopg2.connect(
                host="127.0.0.1", port=5432,
                dbname=dbname, user="postgres",
                password=pwd, connect_timeout=3
            )
            return conn, pwd
        except Exception:
            continue
    return None, None

db_num = 2
for pg_db in pg_databases:
    db_num += 1
    output_lines.append("\n\n" + "━" * 70)
    output_lines.append(f"  [{db_num}] PostgreSQL — {pg_db['db']} (مشروع: {pg_db['project']})")
    output_lines.append("━" * 70)

    if not HAS_PSYCOPG:
        output_lines.append("  ⚠ مكتبة psycopg2 غير مثبتة — يتم التخطي")
        continue

    conn, used_pwd = try_connect(pg_db['db'], passwords_to_try)
    if not conn:
        output_lines.append(f"  ✗ تعذر الاتصال بقاعدة البيانات (تحقق من كلمة المرور)")
        continue

    output_lines.append(f"  ✓ تم الاتصال بنجاح")
    try:
        cur = conn.cursor()

        # Get all tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]
        output_lines.append(f"  عدد الجداول: {len(tables)}")

        for table in tables:
            output_lines.append(f"\n  {'─'*60}")
            output_lines.append(f"  الجدول: {table}")
            output_lines.append(f"  {'─'*60}")

            # Get columns
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='{table}'
                ORDER BY ordinal_position
            """)
            cols_info = cur.fetchall()
            col_names = [c[0] for c in cols_info]
            col_types = [f"{c[0]}({c[1]})" for c in cols_info]
            output_lines.append(f"  الأعمدة: {', '.join(col_types)}")

            # Get row count
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = cur.fetchone()[0]
            output_lines.append(f"  عدد السجلات: {count}")

            # Get first 50 rows
            if count > 0:
                cur.execute(f'SELECT * FROM "{table}" LIMIT 50')
                rows = cur.fetchall()
                output_lines.append(f"\n  البيانات (أول {min(count,50)} سجل):")
                output_lines.append("  " + " | ".join(col_names))
                output_lines.append("  " + "-" * min(80, len(" | ".join(col_names)) + 4))
                for row in rows:
                    row_str = " | ".join([str(v)[:30] if v is not None else "NULL" for v in row])
                    output_lines.append("  " + row_str)
                if count > 50:
                    output_lines.append(f"\n  ... و {count - 50} سجل إضافي")
    except Exception as e:
        output_lines.append(f"  خطأ أثناء الاستعلام: {e}")
    finally:
        conn.close()

# ────────────────────────────────────────────────────────────────
# Save to file
# ────────────────────────────────────────────────────────────────
output_lines.append("\n\n" + "=" * 70)
output_lines.append("  نهاية التقرير")
output_lines.append("=" * 70)

output_text = "\n".join(output_lines)
output_file = r"C:\Users\Roots\Desktop\database_report.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"✓ تم حفظ التقرير في: {output_file}")
print(f"  عدد الأسطر: {len(output_lines)}")
