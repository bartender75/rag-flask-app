# 使用官方 Python 映像
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製程式與需求檔
COPY . /app
COPY requirements.txt .

# 安裝依賴套件
# RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -i https://pypi.org/simple -r requirements.txt

# 啟動 Flask 服務
CMD ["python", "app.py"]
