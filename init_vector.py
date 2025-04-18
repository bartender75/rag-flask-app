from chromadb import HttpClient
import psycopg2
import os

# === 刪除 Chroma 向量庫 ===
client = HttpClient(host="localhost", port=8000)
client.delete_collection("documents")
client.create_collection(name="documents", metadata={"hnsw:space": "cosine"})
print("✅ Chroma 向量資料庫重建完成")

# === 刪除 PostgreSQL 資料 ===
print("🔁 連線 PostgreSQL 資料庫中...")

# ✅ 對應你目前 .env 檔內的變數名稱
conn = psycopg2.connect(
    host=os.getenv("PG_HOST", "127.0.0.1"),
    port=os.getenv("PG_PORT", "5439"),
    dbname=os.getenv("PG_DB", "rag_platform"),     # ← 對應你用 PG_DB
    user=os.getenv("PG_USER", "postgres"),
    password=os.getenv("PG_PASSWORD", "")          # ← 這一項已正確命名
)

cur = conn.cursor()

tables = ["query_paragraphs", "queries", "paragraphs", "files"]
for table in tables:
    cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
    print(f"🧹 已清空資料表：{table}")

conn.commit()
cur.close()
conn.close()

print("✅ PostgreSQL 資料表已清空並重置 ID")
