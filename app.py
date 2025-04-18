from flask import Flask, render_template, request, flash, send_from_directory, redirect, url_for
from markupsafe import Markup
from markdown import markdown
import os
import shutil
from dotenv import load_dotenv
from uploader import extract_text_from_file
from vector_store import add_to_vector_store, query_similar
from db import insert_file, insert_query, insert_query_paragraph, get_uploaded_files, get_uploaded_files_count, \
    delete_file_by_id, get_paragraph_by_chroma_id, get_file_by_id
from llm import ask_gpt_summary

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'xlsx'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.template_filter("markdown")
def markdown_filter(text):
    return Markup(markdown(text))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route("/uploads/<path:filename>")
def download_file(filename):
    try:
        print(f"🔍 嘗試下載檔案: {filename}")
        # 檢查文件是否存在於上傳目錄
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(filepath):
            print(f"✅ 檔案存在，準備下載: {filepath}")
            return send_from_directory(directory=app.config['UPLOAD_FOLDER'],
                                       path=filename,
                                       as_attachment=True)
        else:
            print(f"⚠️ 檔案不存在: {filepath}")
            flash(f"找不到檔案: {filename}", "warning")
            return redirect(url_for('index'))
    except Exception as e:
        print(f"❌ 下載檔案時發生錯誤: {str(e)}")
        flash(f"下載檔案時發生錯誤: {str(e)}", "danger")
        return redirect(url_for('index'))


@app.route("/delete/<int:file_id>", methods=['POST'])
def delete_file(file_id):
    delete_file_by_id(file_id)
    return redirect(url_for('index'))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file.filename == "":
                flash("未選擇任何檔案", "warning")
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = file.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                extension = filename.rsplit('.', 1)[1].lower()
                file_id = insert_file(filename, extension, filepath)

                # 萃取文字、分段並存入 DB + 向量庫
                paragraphs = extract_text_from_file(filepath, file.filename)
                add_to_vector_store(paragraphs, file_id, file.filename)

                flash("✅ 上傳與處理完成", "success")
                return redirect(url_for("index"))
            else:
                flash("檔案格式不支援", "danger")
                return redirect(request.url)

        elif "question" in request.form:
            q = request.form["question"]
            query_id = insert_query(q)
            result = query_similar(q)

            print(f"🔍 查詢文字：{q}")
            print(f"🔁 query_similar() 回傳筆數：{len(result)}")
            if result:
                print(f"🔁 第一筆：{result[0]}")

            enriched_results = []
            seen_contents = set()  # 用於追蹤已處理的內容，避免重複

            for i, r in enumerate(result):
                chroma_id = r.get("chroma_id")
                print(f"🔎 嘗試查找段落：chroma_id = {chroma_id}")

                # 從 result 中提取文本內容
                content = r.get("text", "")

                # 如果內容為空或已經加入過，則跳過（避免重複內容）
                if not content or content in seen_contents:
                    continue

                seen_contents.add(content)

                # 先直接從 result 中取得資訊
                paragraph_id = r.get("paragraph_id", "")
                file_id = r.get("file_id", "")

                # 嘗試從資料庫中查詢段落
                paragraph = get_paragraph_by_chroma_id(chroma_id)

                # 初始化變數，確保它們總是被定義
                filename = "未知檔案"
                paragraph_index = "未知"
                file_path = None  # 預設值為 None

                # 如果從資料庫找到段落資料
                if paragraph:
                    para_id = paragraph["id"]
                    insert_query_paragraph(query_id, para_id, i + 1)

                    file_info = get_file_by_id(paragraph["file_id"])
                    if file_info:
                        # 取得檔案名，直接使用 filename，不要分割
                        filename = file_info["filename"]
                        # 使用 full_path 欄位獲取完整路徑
                        file_path = file_info["full_path"]

                        # 檢查檔案是否存在
                        if os.path.exists(file_path):
                            # 設置檔案名為檔案的基本名稱(不包含路徑)
                            print(f"✅ 找到文件: {os.path.basename(file_path)}")
                        else:
                            # 如果檔案不存在，提供更詳細的錯誤信息
                            print(f"⚠️ 檔案路徑不存在: {file_path}")
                            # 嘗試檢查是否有其他路徑可用
                            uploads_dir = app.config['UPLOAD_FOLDER']
                            potential_file = os.path.join(uploads_dir, os.path.basename(file_path))
                            if os.path.exists(potential_file):
                                file_path = potential_file
                                print(f"✅ 在上傳目錄找到文件: {file_path}")
                            else:
                                file_path = None

                    paragraph_index = paragraph["paragraph_index"]
                else:
                    # 如果資料庫中沒有，但有 file_id
                    if file_id:
                        try:
                            file_id_int = int(file_id) if isinstance(file_id, str) and file_id.isdigit() else file_id
                            file_info = get_file_by_id(file_id_int)
                            if file_info:
                                filename = file_info["filename"]
                                # 直接使用 filename 作為下載路徑，因為 download_file 函數會自動在 UPLOAD_FOLDER 中尋找
                                file_path = filename
                                # 從資料庫取得的路徑可能是相對路徑，檢查是否需要調整
                                if file_path and not os.path.isabs(file_path):
                                    # 如果是相對路徑，直接使用檔案名稱即可，因為下載路由會正確處理
                                    filename_only = os.path.basename(file_path)
                                else:
                                    filename_only = filename
                        except Exception as e:
                            print(f"⚠️ 處理 file_id={file_id} 時出錯: {str(e)}")

                    # 使用 chroma_id 解析出檔案 ID 和段落索引
                    if isinstance(chroma_id, str) and "-" in chroma_id:
                        parts = chroma_id.split("-")
                        if len(parts) >= 2:
                            # 如果 paragraph_id 為空，用 chroma_id 的第二部分
                            if not paragraph_id:
                                paragraph_id = parts[1]
                            # 嘗試從 chroma_id 解析出檔案識別符（如 V2.0）
                            if not filename or filename == "未知檔案":
                                # 假設檔案識別符可能在 chroma_id 中
                                if len(parts) > 2 and parts[0]:
                                    filename = f"檔案 {parts[0]}"

                    # 處理 paragraph_id 可能是字串或數字的情況
                    if paragraph_id:
                        # 如果是字串，檢查是否為數字字串
                        if isinstance(paragraph_id, str):
                            if paragraph_id.isdigit():  # 只有字串才能使用 isdigit()
                                paragraph_index = paragraph_id
                        # 如果是數字類型，直接使用
                        elif isinstance(paragraph_id, (int, float)):
                            paragraph_index = str(int(paragraph_id))  # 轉為整數再轉字串，去除小數部分

                # 轉換段落索引為整數顯示（如果可能）
                try:
                    if isinstance(paragraph_index, str) and paragraph_index.isdigit():
                        paragraph_index = int(paragraph_index)
                    elif isinstance(paragraph_index, (int, float)):
                        paragraph_index = int(paragraph_index)
                except:
                    paragraph_index = "未知"

                # 添加到結果中，確保所有字段都已定義
                enriched_results.append({
                    "filename": filename,
                    "paragraph_index": paragraph_index,
                    "content": content,
                    "score": r["score"],
                    "file_path": file_path
                })

            # 如果有結果，則使用 GPT 生成摘要
            if enriched_results:
                # 確保 enriched_results 的格式一致，替換 'content' 為 'text' 如果需要的話
                for result in enriched_results:
                    if 'content' in result and 'text' not in result:
                        result['text'] = result['content']
                gpt_answer = ask_gpt_summary(q, enriched_results)
            else:
                gpt_answer = "抱歉，找不到相關資訊。"

            print(f"📦 enriched_results 最終筆數：{len(enriched_results)}")
            return render_template("index.html",
                                   query=q,
                                   result=enriched_results,
                                   gpt_answer=gpt_answer,
                                   uploaded_files=get_uploaded_files(),
                                   total=len(enriched_results),
                                   per_page=10
                                   )

        else:
            flash("未知的請求類型", "warning")
            return redirect(url_for("index"))

    # GET 請求處理
    return render_template("index.html",
                           uploaded_files=get_uploaded_files()
                           )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)