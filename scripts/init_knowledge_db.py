import sqlite3
import os

DB_PATH = "data/knowledge.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        upload_time TEXT NOT NULL,
        file_size INTEGER,
        status TEXT DEFAULT 'indexed'
    )
    """)
    
    conn.commit()
    conn.close()
    print(f"Initialized knowledge database at {DB_PATH}")

if __name__ == "__main__":
    init_db()
