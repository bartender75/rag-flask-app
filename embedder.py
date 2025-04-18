from sentence_transformers import SentenceTransformer

# 使用 text2vec-base-multilingual 模型（支援多語言）
model_name = "shibing624/text2vec-base-multilingual"
model = SentenceTransformer(model_name)

def to_embedding(text):
    return model.encode(text, convert_to_numpy=True)
