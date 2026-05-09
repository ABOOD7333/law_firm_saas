from database.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    db.execute(text("ALTER TABLE law_hearings ADD COLUMN attachment_path TEXT;"))
    db.commit()
    print("Successfully added attachment_path to law_hearings")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
