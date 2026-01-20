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
        status TEXT DEFAULT 'indexed',
        knowledge_type TEXT DEFAULT 'product_raw',
        folder TEXT DEFAULT ''
    )
    """)

    # 迁移：为旧数据库添加缺失的字段
    migrations = [
        ("knowledge_type", "ALTER TABLE documents ADD COLUMN knowledge_type TEXT DEFAULT 'product_raw'"),
        ("folder", "ALTER TABLE documents ADD COLUMN folder TEXT DEFAULT ''"),
    ]
    for col_name, sql in migrations:
        try:
            cursor.execute(sql)
            print(f"Added {col_name} column to existing table")
        except sqlite3.OperationalError:
            # 字段已存在，忽略
            pass

    conn.commit()
    conn.close()
    print(f"Initialized knowledge database at {DB_PATH}")

if __name__ == "__main__":
    init_db()