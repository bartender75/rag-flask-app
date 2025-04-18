import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_gpt_summary(question, paragraphs):
    prompt = build_prompt(question, paragraphs)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": "你是知識助理，請根據提供段落，以繁體中文整理出完整摘要，使用 Markdown 格式回覆，並遵守以下規則：\n\n"
                           "概述：\n請用 100～150 字說明主旨與背景脈絡，文字請勿少於 100 字。\n\n"
                           "接下來請條列重點內容：\n"
                           "每一項以「**重點 n：**」開頭（n 為數字），內容請不少於 50 字。\n"
                           "請至少列出 3 項，若內容豐富可列出 5 項以上。\n"
                           "請將每個重點段落之間用空行分隔，確保 Markdown 呈現為獨立段落。\n"
                           "請不要在回答中直接顯示 '\\n\\n' 這樣的字符。"
            },
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


def build_prompt(question, paragraphs):
    try:
        # 檢查每個段落是否包含 'content' 或 'text' 鍵
        context_parts = []
        for i, p in enumerate(paragraphs):
            if 'content' in p:
                context_parts.append(f"{i + 1}. {p['content']}")
            elif 'text' in p:
                context_parts.append(f"{i + 1}. {p['text']}")
            else:
                # 如果既沒有 'content' 也沒有 'text'，則尋找任何可能的文本字段
                for key, value in p.items():
                    if isinstance(value, str) and len(value) > 20:
                        context_parts.append(f"{i + 1}. {value}")
                        break
                else:
                    # 如果找不到任何合適的文本字段，使用整個字典的字串表示
                    context_parts.append(f"{i + 1}. {str(p)}")

        context = "\n\n".join(context_parts)
        return f"""以下是相關資料段落：

{context}

請根據上面資料，回答以下問題：
「{question}」
"""
    except Exception as e:
        print(f"⚠️ 構建提示時出錯: {str(e)}")
        # 如果出錯，返回一個簡單的提示
        return f"""請回答以下問題 (備註：由於文本處理錯誤，提供的上下文可能不完整)：
「{question}」
"""


def extract_keywords(text, top_k=5):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是關鍵字抽取助手。請從輸入段落中，僅提取 3 至 5 個具主題意涵的繁體中文『關鍵詞』或短語，每個建議為 2～6 字。\n"
                    "請優先選擇專有名詞、技術詞、主題名詞等（例如：權限設定、資安政策、認證流程）。\n"
                    "請避免使用動詞（如使用、下載）、副詞（如快速）、形容詞或無意義詞語。\n"
                    "請使用半形逗號分隔詞語，直接回傳關鍵詞列表，不要補充說明。"
                )
            },
            {
                "role": "user",
                "content": text
            }
        ]
    )
    return response.choices[0].message.content.strip()