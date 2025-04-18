
#專案目錄
cd /mnt/d/workspace/workspace-rag/rag-flask-app


#查看docker
docker ps

#啟動 docker chroma
docker run -p 8000:8000 -v chroma_data:/data chromadb/chroma

#查占用port號
sudo lsof -i :8000

#砍掉佔port的PID
sudo kill -9 73982 73990

#列出目前所有（包含已停止）container
docker ps -a

#刪除這個 container
docker rm -f epic_spence