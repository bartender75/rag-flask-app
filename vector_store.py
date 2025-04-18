import os
import re
import chromadb
from embedder import to_embedding
from db import insert_paragraph
from llm import extract_keywords
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()

chroma_host = os.getenv("CHROMA_HOST", "localhost")
chroma_port = os.getenv("CHROMA_PORT", "8000")
collection_name = os.getenv("CHROMA_COLLECTION", "rag_demo")

client = chromadb.HttpClient(host=chroma_host, port=int(chroma_port))

try:
    collection = client.get_collection(collection_name)
except:
    collection = client.create_collection(collection_name)


def add_to_vector_store(paragraphs, file_id, filename):
    print(f"✅ 新增段落向量：{len(paragraphs)} 筆\n")

    for idx, text in enumerate(paragraphs):
        chroma_id = f"{file_id}-{idx}"
        embedding = to_embedding(text)

        # Step 1: GPT 抽出原始關鍵詞
        raw_keywords = extract_keywords(text)
        cleaned = clean_keywords(raw_keywords)

        # print("⚠ GPT 原始關鍵字：", raw_keywords)
        # Step 2: 使用 TF-IDF 對 cleaned 關鍵詞做排序過濾
        # final_keywords = extract_keywords_tfidf(text, cleaned)
        final_keywords = "、".join(cleaned)

        # 確保 metadata 中的 paragraph_id 是字串類型
        collection.add(
            ids=[chroma_id],
            embeddings=[embedding],
            documents=[text],
            metadatas={
                "file_id": str(file_id),
                "filename": filename,
                "paragraph_id": str(idx)  # 確保是字串格式
            }
        )

        # 將 chroma_id 儲存到資料庫中，確保與 Chroma 中的 ID 一致
        insert_paragraph(file_id, idx, text, chroma_id, final_keywords)


# 在 vector_store.py 中修改相似度計算
def query_similar(query_text, top_k=5):
    query_embedding = to_embedding(query_text)
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k,
                               include=["metadatas", "distances", "documents"])

    similar_results = []

    # 檢查回傳的結果是否為空
    if not results["ids"] or len(results["ids"][0]) == 0:
        print("⚠️ 查詢結果為空")
        return similar_results

    for i, meta in enumerate(results["metadatas"][0]):
        chroma_id = results["ids"][0][i]
        file_id = meta.get("file_id", "")
        paragraph_id = meta.get("paragraph_id", "")

        # 簡化相似度計算，直接使用 Chroma 返回的餘弦相似度
        distance = results["distances"][0][i]
        # 相似度計算：餘弦距離轉為相似度百分比
        similarity = min(max((1 - distance) * 100, 0), 100)  # 確保在 0-100% 之間

        document = results["documents"][0][i]
        print(f"🔢 原始距離值: {distance}, 計算後相似度: {similarity}%")
        similar_results.append({
            "chroma_id": chroma_id,
            "score": similarity,  # 相似度百分比
            "paragraph_id": paragraph_id,
            "file_id": file_id,
            "text": document
        })

    return similar_results


def clean_keywords(raw_keywords: str) -> list:
    return [
        re.sub(r"[^\w\d一-龥]", "", kw).strip()
        for kw in raw_keywords.split(",")
        if 1 < len(kw.strip()) <= 8
    ]


def extract_keywords_tfidf(text, candidate_keywords: list, top_k=10) -> str:
    if not candidate_keywords:
        return ""

    vectorizer = TfidfVectorizer(vocabulary=candidate_keywords, token_pattern=r"(?u)\b\w+\b")
    tfidf_matrix = vectorizer.fit_transform([text])
    scores = zip(vectorizer.get_feature_names_out(), tfidf_matrix.toarray()[0])
    sorted_keywords = sorted(scores, key=lambda x: x[1], reverse=True)

    return "、".join([word for word, _ in sorted_keywords[:top_k]])