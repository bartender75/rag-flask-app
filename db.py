import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# 讀取 .env 環境變數
load_dotenv()

# 從環境變數取得 DB 設定
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5439")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "66073888")
PG_DB = os.getenv("PG_DB", "rag_platform")

# 初始化連線
conn = psycopg2.connect(
    host=PG_HOST,
    port=PG_PORT,
    dbname=PG_DB,
    user=PG_USER,
    password=PG_PASSWORD
)
conn.autocommit = True

def insert_file(filename, extension, full_path):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO files (filename, extension, full_path)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (filename, extension, full_path))
        return cur.fetchone()[0]

def insert_paragraph(file_id, index, content, chroma_id, keywords=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO paragraphs (file_id, paragraph_index, content, chroma_id, keywords)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (file_id, index, content, chroma_id, keywords))
        return cur.fetchone()[0]

def insert_query(query_text):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO queries (query_text)
            VALUES (%s)
            RETURNING id;
        """, (query_text,))
        return cur.fetchone()[0]

def insert_query_paragraph(query_id, paragraph_id, rank):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO query_paragraphs (query_id, paragraph_id, rank)
            VALUES (%s, %s, %s);
        """, (query_id, paragraph_id, rank))


def get_paragraph_by_chroma_id(chroma_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 先嘗試精確匹配
        cur.execute("SELECT * FROM paragraphs WHERE chroma_id = %s;", (chroma_id,))
        result = cur.fetchone()

        # 如果找不到結果，打印日誌訊息，可在測試時提供信息
        if not result:
            print(f"⚠️ 無法在資料庫中找到 chroma_id={chroma_id}")

            # 嘗試模糊匹配，有時候 chroma_id 可能有不同的格式
            # 例如: "21-29" 和 "21-29-1" 或者其他變化
            parts = chroma_id.split('-')
            if len(parts) >= 2:
                file_id = parts[0]
                paragraph_index = parts[1]

                cur.execute("SELECT * FROM paragraphs WHERE file_id = %s AND paragraph_index = %s;",
                            (file_id, paragraph_index))
                result = cur.fetchone()

                if result:
                    print(f"✅ 通過 file_id={file_id} 和 paragraph_index={paragraph_index} 找到段落")

        return result

def get_filename_by_file_id(file_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT filename, full_path FROM files WHERE id = %s;", (file_id,))
        return cur.fetchone()

def get_all_queries_with_results():
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                q.id AS query_id,
                q.query_text,
                to_char(q.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                p.content,
                p.paragraph_index,
                p.keywords,
                f.filename
            FROM queries q
            JOIN query_paragraphs qp ON q.id = qp.query_id
            JOIN paragraphs p ON qp.paragraph_id = p.id
            JOIN files f ON p.file_id = f.id
            ORDER BY q.created_at DESC, qp.rank ASC;
        """)
        return cur.fetchall()

def get_uploaded_files(limit=5, offset=0):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT f.id, f.filename, f.full_path AS filepath,
                   f.created_at,
                   COUNT(p.id) AS paragraphs,
                   CASE WHEN COUNT(p.id) > 0 THEN '已處理' ELSE '處理中' END AS status
            FROM files f
            LEFT JOIN paragraphs p ON f.id = p.file_id
            GROUP BY f.id
            ORDER BY f.created_at DESC
            LIMIT %s OFFSET %s;
        """, (limit, offset))
        results = cur.fetchall()
        # 加上 keywords 一併處理
        for f in results:
            f["keywords"] = get_keywords_by_file(f["id"])
        return results

def get_uploaded_files_count():
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM files;")
        return cur.fetchone()[0]

def delete_file_by_filename(filename):
    with conn.cursor() as cur:
        # 找到 file id
        cur.execute("SELECT id FROM files WHERE filename = %s", (filename,))
        result = cur.fetchone()
        if not result:
            raise Exception("檔案不存在")
        file_id = result[0]

        # 刪除段落與查詢關聯
        cur.execute("DELETE FROM query_paragraphs WHERE paragraph_id IN (SELECT id FROM paragraphs WHERE file_id = %s)", (file_id,))
        cur.execute("DELETE FROM paragraphs WHERE file_id = %s", (file_id,))
        cur.execute("DELETE FROM files WHERE id = %s", (file_id,))

def delete_file_by_id(file_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM query_paragraphs WHERE paragraph_id IN (SELECT id FROM paragraphs WHERE file_id = %s)", (file_id,))
        cur.execute("DELETE FROM paragraphs WHERE file_id = %s", (file_id,))
        cur.execute("DELETE FROM files WHERE id = %s", (file_id,))

def get_keywords_by_file(file_id):
    with conn.cursor() as cur:
        cur.execute("SELECT keywords FROM paragraphs WHERE file_id = %s", (file_id,))
        rows = cur.fetchall()
        merged = set()
        for row in rows:
            if row[0]:
                merged.update(row[0].split("、"))
        return "、".join(sorted(merged))

def get_file_id_by_filename(filename):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM files WHERE filename = %s", (filename,))
        row = cur.fetchone()
        return row[0] if row else None


def get_file_by_id(file_id):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 嘗試將 file_id 轉為整數處理
            file_id_int = int(file_id) if isinstance(file_id, str) else file_id
            cur.execute("SELECT * FROM files WHERE id = %s", (file_id_int,))
            result = cur.fetchone()

            if not result:
                print(f"⚠️ 找不到 ID 為 {file_id} 的檔案")

            return result
    except Exception as e:
        print(f"⚠️ 查詢檔案時發生錯誤 (file_id={file_id}): {str(e)}")
        return None
