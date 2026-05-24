# Dự án mới: RAG Chatbot cho sinh viên

Phiên bản đơn giản hóa từ dự án hiện tại.  
Mục tiêu: bảo vệ đồ án môn học, demo được, giải thích được, dễ setup.

---

## So sánh với dự án hiện tại

| Thứ | Dự án hiện tại | Dự án mới |
|-----|---------------|-----------|
| Backend | Spring Boot (Java) + FastAPI (Python) | **Chỉ FastAPI (Python)** |
| Vector DB | Qdrant (Docker container riêng) | **ChromaDB (embedded, không cần Docker)** |
| Database | MySQL (Docker container riêng) | **SQLite (file .db tự tạo)** |
| Auth | JWT + Spring Security | **Không có auth (demo local)** |
| Proxy | Nginx | **Không cần** |
| Deploy | Docker Compose nhiều service | **Chạy thẳng `uvicorn` + `npm dev`** |
| Folder | `rag-api/`, `backend-spring/`, `frontend/` | **`backend/`, `frontend/`** |

---

## Tech stack

```
backend/   →  Python 3.11+  FastAPI  ChromaDB  SQLite  pypdf  sentence-transformers  openai
frontend/  →  React 18  Vite  axios  TailwindCSS
```

**Lý do chọn:**
- **ChromaDB**: nhúng thẳng vào Python, không cần cài server riêng. Data lưu trong folder `data/chroma/`.
- **SQLite**: file `.db` duy nhất, zero setup, đủ cho demo/local.
- **sentence-transformers**: chạy local không cần API key (hoặc dùng OpenAI embeddings nếu muốn đơn giản hơn).
- **FastAPI**: 1 file `main.py` là có thể chạy, dễ giải thích khi bảo vệ.

---

## Cấu trúc thư mục

```
rag-chatbot-student/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py       # upload, list, delete PDF
│   │   │   ├── knowledge_bases.py # CRUD knowledge base
│   │   │   └── chat.py            # hỏi đáp, lịch sử chat
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ingest.py          # parse PDF → chunk → embed → lưu ChromaDB
│   │   │   ├── retrieval.py       # tìm chunk liên quan từ ChromaDB
│   │   │   └── llm.py             # gọi OpenAI tạo câu trả lời
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # SQLAlchemy engine (SQLite)
│   │   │   └── models.py          # ORM models
│   │   ├── schemas.py             # Pydantic request/response
│   │   ├── config.py              # settings từ .env
│   │   └── main.py                # FastAPI app, mount routers
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js          # axios wrapper
│   │   ├── components/
│   │   │   ├── ChatBox.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── SourceList.jsx
│   │   │   └── DocumentCard.jsx
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx
│   │   │   └── KnowledgePage.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── uploads/          # PDF files (auto-created)
├── data/
│   ├── app.db        # SQLite (auto-created)
│   └── chroma/       # ChromaDB (auto-created)
├── .env.example
└── README.md
```

---

## Database schema (SQLite)

```sql
-- Knowledge Bases
CREATE TABLE knowledge_bases (
    id          TEXT PRIMARY KEY,   -- UUID
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL       -- ISO datetime string
);

-- Documents (PDF files)
CREATE TABLE documents (
    id                TEXT PRIMARY KEY,   -- UUID
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases(id),
    file_name         TEXT NOT NULL,
    file_path         TEXT NOT NULL,      -- đường dẫn trong uploads/
    total_pages       INTEGER,
    total_chunks      INTEGER,
    status            TEXT NOT NULL,      -- 'processing' | 'done' | 'failed'
    created_at        TEXT NOT NULL
);

-- Chat Sessions
CREATE TABLE chat_sessions (
    id                TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases(id),
    title             TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

-- Chat Messages
CREATE TABLE chat_messages (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role       TEXT NOT NULL,   -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    sources    TEXT,            -- JSON string: [{file_name, page, score}]
    created_at TEXT NOT NULL
);
```

---

## ChromaDB — Collection duy nhất

```
collection name: "chunks"

Mỗi document khi ingest → thêm entries vào collection này.

Metadata của mỗi entry:
{
    "knowledge_base_id": "...",
    "document_id":       "...",
    "file_name":         "...",
    "page":              3,
    "chunk_index":       7
}

Khi query → filter theo knowledge_base_id để lấy chunk của KB đó.
```

---

## API Endpoints

### Knowledge Bases

```
POST   /api/knowledge-bases            Tạo KB mới
GET    /api/knowledge-bases            Lấy danh sách tất cả KB
GET    /api/knowledge-bases/{id}       Chi tiết KB + list documents
DELETE /api/knowledge-bases/{id}       Xóa KB (xóa luôn docs + chunks)
```

### Documents

```
POST   /api/knowledge-bases/{kb_id}/documents        Upload PDF (multipart/form-data)
DELETE /api/knowledge-bases/{kb_id}/documents/{id}   Xóa PDF khỏi KB
```

### Chat

```
POST   /api/chat/sessions              Tạo session mới {knowledge_base_id, title}
GET    /api/chat/sessions              List sessions
GET    /api/chat/sessions/{id}         Chi tiết session + messages
POST   /api/chat/sessions/{id}/ask     Hỏi câu hỏi {question}
DELETE /api/chat/sessions/{id}         Xóa session
```

---

## Core logic

### Ingest pipeline (`backend/app/services/ingest.py`)

```
1. Nhận file PDF, lưu vào uploads/{document_id}.pdf
2. Parse từng trang bằng pypdf → list[str]
3. Chunk mỗi trang: nếu text > 600 token thì cắt, overlap 100 token
4. Embed từng chunk bằng sentence-transformers hoặc OpenAI
5. Upsert vào ChromaDB với metadata (kb_id, doc_id, file_name, page, chunk_index)
6. Update document.status = 'done', total_chunks vào SQLite
```

### Retrieval + Answer (`backend/app/services/retrieval.py`, `llm.py`)

```
1. Embed câu hỏi
2. ChromaDB query(n_results=5, where={"knowledge_base_id": kb_id})
3. Lấy top 5 chunks + metadata
4. Build prompt:
   [System] Bạn là trợ lý học tập. Chỉ dựa vào tài liệu sau để trả lời...
   [Context] Chunk 1 (file: A.pdf, trang 3): ...
             Chunk 2 (file: B.pdf, trang 7): ...
   [User] Câu hỏi của người dùng
5. Gọi OpenAI chat completion
6. Trả về {answer, sources: [{file_name, page, score}]}
```

---

## Config (`backend/.env.example`)

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Hoặc dùng local embedding (không cần API key)
EMBEDDING_MODE=local
# EMBEDDING_MODE=openai

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
CHUNK_SIZE=600
CHUNK_OVERLAP=100
TOP_K=5

UPLOAD_DIR=./uploads
DATA_DIR=./data
```

---

## Khởi chạy

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # điền OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                   # chạy ở localhost:5173
```

Mở `http://localhost:5173` → tạo Knowledge Base → upload PDF → chat.

---

## requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9       # upload file
pydantic-settings==2.4.0
pypdf==5.1.0                  # parse PDF
chromadb==0.5.15              # vector DB embedded
sentence-transformers==3.2.1  # local embedding
openai==1.50.0                # LLM + optional OpenAI embedding
sqlalchemy==2.0.36            # ORM cho SQLite
python-dotenv==1.0.1
```

---

## package.json dependencies (frontend)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0",
    "axios": "^1.7.7"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.2",
    "vite": "^5.4.9",
    "tailwindcss": "^3.4.13",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47"
  }
}
```

---

## Các file cần viết (theo thứ tự)

```
Bước 1 — Khung dự án
  backend/app/main.py          FastAPI app, CORS, mount routers
  backend/app/config.py        Settings từ .env
  backend/app/db/database.py   SQLAlchemy engine SQLite
  backend/app/db/models.py     4 bảng ORM
  backend/app/schemas.py       Pydantic schemas cho tất cả request/response

Bước 2 — Knowledge Base + Document API
  backend/app/api/knowledge_bases.py   CRUD KB
  backend/app/api/documents.py         Upload + delete PDF

Bước 3 — Ingest service
  backend/app/services/ingest.py       Pipeline: parse → chunk → embed → ChromaDB

Bước 4 — Chat API
  backend/app/api/chat.py              Session + ask endpoint
  backend/app/services/retrieval.py    ChromaDB search
  backend/app/services/llm.py          OpenAI prompt + call

Bước 5 — Frontend
  frontend/src/api/client.js           axios instance
  frontend/src/pages/KnowledgePage.jsx tạo/xem KB, upload PDF
  frontend/src/pages/ChatPage.jsx      giao diện chat
  frontend/src/components/...          ChatBox, MessageBubble, SourceList

Bước 6 — Polish
  README.md                            hướng dẫn chạy
  Kiểm tra với 2-3 PDF thật
```

---

## Sơ đồ luồng hệ thống (cho slide bảo vệ)

```
[User upload PDF]
      ↓
[FastAPI /documents]
      ↓
[IngestService]
  pypdf.parse() → text từng trang
  chunk() → đoạn nhỏ ~600 token
  embed() → vector 384 chiều
  ChromaDB.add() → lưu vector + metadata
      ↓
[SQLite] lưu metadata document, status=done

[User hỏi câu hỏi]
      ↓
[FastAPI /chat/ask]
      ↓
[RetrievalService]
  embed(question) → query vector
  ChromaDB.query(filter={kb_id}) → top 5 chunks gần nhất
      ↓
[LlmService]
  build_prompt(question, chunks) → prompt
  OpenAI.chat() → câu trả lời
      ↓
[Response] {answer, sources:[{file, page, score}]}
      ↓
[SQLite] lưu message vào chat_sessions
```

---

## Gợi ý tên dự án

- `study-rag` / `thesis-rag`
- `dochat` (document + chat)
- `pdfmate`

---

## Những gì KHÔNG làm trong phiên bản này

- Auth / đăng nhập → không cần cho demo local
- Async ingest (job queue) → chạy sync, PDF nhỏ < 50 trang là đủ nhanh
- Reranker model → ChromaDB cosine similarity đủ dùng
- Streaming response → trả về 1 lần cho đơn giản
- Docker / Nginx → chạy thẳng lệnh uvicorn + npm dev
- Đa người dùng → chỉ 1 user local

Những thứ trên là P1/P2 trong dự án hiện tại, hoàn toàn có thể bổ sung sau khi bảo vệ xong.
