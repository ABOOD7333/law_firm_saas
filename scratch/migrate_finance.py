import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        print("[INFO] Connecting to PostgreSQL database...")
        return psycopg2.connect(DATABASE_URL)
    else:
        db_path = "law_firm.db"
        print(f"[INFO] Connecting to local SQLite database: {db_path}")
        return sqlite3.connect(db_path)

def migrate():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Migrate law_transactions
    print("[INFO] Migrating law_transactions table...")
    try:
        if DATABASE_URL and DATABASE_URL.startswith("postgres"):
            cursor.execute("ALTER TABLE law_transactions ADD COLUMN currency VARCHAR(10) DEFAULT 'SAR';")
        else:
            cursor.execute("ALTER TABLE law_transactions ADD COLUMN currency TEXT DEFAULT 'SAR';")
        print("[SUCCESS] Added 'currency' column to law_transactions.")
    except Exception as e:
        print(f"[WARNING] Could not add 'currency' to law_transactions (likely already exists): {e}")
        
    try:
        if DATABASE_URL and DATABASE_URL.startswith("postgres"):
            cursor.execute("ALTER TABLE law_transactions ADD COLUMN exchange_rate DOUBLE PRECISION DEFAULT 1.0;")
        else:
            cursor.execute("ALTER TABLE law_transactions ADD COLUMN exchange_rate REAL DEFAULT 1.0;")
        print("[SUCCESS] Added 'exchange_rate' column to law_transactions.")
    except Exception as e:
        print(f"[WARNING] Could not add 'exchange_rate' to law_transactions (likely already exists): {e}")

    # 2. Migrate law_expenses
    print("[INFO] Migrating law_expenses table...")
    try:
        if DATABASE_URL and DATABASE_URL.startswith("postgres"):
            cursor.execute("ALTER TABLE law_expenses ADD COLUMN currency VARCHAR(10) DEFAULT 'SAR';")
        else:
            cursor.execute("ALTER TABLE law_expenses ADD COLUMN currency TEXT DEFAULT 'SAR';")
        print("[SUCCESS] Added 'currency' column to law_expenses.")
    except Exception as e:
        print(f"[WARNING] Could not add 'currency' to law_expenses (likely already exists): {e}")
        
    try:
        if DATABASE_URL and DATABASE_URL.startswith("postgres"):
            cursor.execute("ALTER TABLE law_expenses ADD COLUMN exchange_rate DOUBLE PRECISION DEFAULT 1.0;")
        else:
            cursor.execute("ALTER TABLE law_expenses ADD COLUMN exchange_rate REAL DEFAULT 1.0;")
        print("[SUCCESS] Added 'exchange_rate' column to law_expenses.")
    except Exception as e:
        print(f"[WARNING] Could not add 'exchange_rate' to law_expenses (likely already exists): {e}")

    # 3. Update existing records if they have null values
    print("[INFO] Setting default values for existing records...")
    try:
        cursor.execute("UPDATE law_transactions SET currency = 'SAR' WHERE currency IS NULL;")
        cursor.execute("UPDATE law_transactions SET exchange_rate = 1.0 WHERE exchange_rate IS NULL;")
        cursor.execute("UPDATE law_expenses SET currency = 'SAR' WHERE currency IS NULL;")
        cursor.execute("UPDATE law_expenses SET exchange_rate = 1.0 WHERE exchange_rate IS NULL;")
        conn.commit()
        print("[SUCCESS] Default values updated.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to set default values: {e}")

    conn.close()
    print("[INFO] Migration finished successfully.")

if __name__ == "__main__":
    migrate()
