# AI 法律咨询小助手 MVP

## 启动

### 1. 后端
cd backend
python -m venv venv
# 激活虚拟环境：Windows 用 venv\Scripts\activate ；Mac/Linux 用 source venv/bin/activate
# CPU 版 torch（避免误装数 GB 的 CUDA 版）：
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
cp .env.example .env  # 填入 ZHIPUAI_API_KEY
python knowledge_base.py  # 建向量库（首次下载 BGE 模型约 400MB）
uvicorn main:app --reload --port 8000

### 2. 前端
cd frontend
npm install
npm run dev
# 打开 http://localhost:3000
