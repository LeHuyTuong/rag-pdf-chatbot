# RAG Service — Standalone spec

Chỉ phụ trách phần `rag/`.  
Team khác lo frontend và các service còn lại.

---

## Cloud services dùng (free tier, không cần cài local)

| Service | Dùng để | Free tier | Link đăng ký |
|---------|---------|-----------|-------------|
| **Qdrant Cloud** | Lưu vector embeddings | 1 cluster, 1GB, 0.5M vectors | cloud.qdrant.io |
| **Neo4j AuraDB** | Lưu metadata (KB, Document, Session, Message) dạng graph | 200k nodes, 400k relationships | console.neo4j.io |

Sau khi tạo account:
- Qdrant → lấy `QDRANT_URL` + `QDRANT_API_KEY`
- Neo4j → lấy `NEO4J_URI` (`neo4j+s://xxx.databases.neo4j.io`) + `NEO4J_USER` + `NEO4J_PASSWORD`

---

## Cấu trúc thư mục `rag/`

```
rag/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── ingest.py          # POST /ingest — nhận PDF, trả document_id
│   │   └── chat.py            # POST /ask — nhận question + kb_id
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py      # pypdf → list[{page, text}]
│   │   ├── chunker.py         # text → list[Chunk]
│   │   ├── embedder.py        # list[str] → list[vector]
│   │   ├── qdrant_store.py    # upsert + search Qdrant Cloud
│   │   ├── neo4j_store.py     # CRUD nodes/rels trong Neo4j AuraDB
│   │   └── llm.py             # build prompt + call OpenAI
│   ├── schemas.py             # Pydantic models
│   ├── config.py              # settings từ .env
│   └── main.py                # FastAPI app
├── tests/
│   ├── conftest.py            # fixtures: settings, sample PDF, cleanup
│   ├── unit/
│   │   ├── test_chunker.py
│   │   ├── test_pdf_parser.py
│   │   └── test_prompt_builder.py
│   └── integration/
│       ├── test_ingest.py     # ingest PDF → check Qdrant + Neo4j
│       ├── test_retrieval.py  # query → check chunks trả về
│       └── test_chat.py       # end-to-end: ingest → hỏi → có answer
├── sample_docs/
│   └── test.pdf               # PDF nhỏ dùng cho test (5-10 trang)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Data model

### Qdrant — Collection `rag_chunks`

```
Mỗi chunk được upsert với:

id:      UUID string (chunk_id)
vector:  float[384]  (sentence-transformers embedding)
payload: {
    knowledge_base_id: str,
    document_id:       str,
    file_name:         str,
    page:              int,
    chunk_index:       int,
    text_preview:      str  (100 ký tự đầu, để debug)
}
```

Search filter theo `knowledge_base_id` để lấy chunk của đúng KB.

### Neo4j AuraDB — Graph model

```
Nodes:
  (:KnowledgeBase {id, name, created_at})
  (:Document      {id, kb_id, file_name, status, total_pages, total_chunks, created_at})
  (:ChatSession   {id, kb_id, title, created_at})
  (:Message       {id, session_id, role, content, sources_json, created_at})

Relationships:
  (:KnowledgeBase)-[:HAS_DOCUMENT]->(:Document)
  (:ChatSession)-[:HAS_MESSAGE]->(:Message)

Cypher thường dùng:
  // Tạo KB
  CREATE (:KnowledgeBase {id: $id, name: $name, created_at: $ts})

  // Lấy documents của KB
  MATCH (kb:KnowledgeBase {id: $kb_id})-[:HAS_DOCUMENT]->(d:Document)
  RETURN d

  // Lưu message mới
  MATCH (s:ChatSession {id: $session_id})
  CREATE (s)-[:HAS_MESSAGE]->(:Message {id: $id, role: $role, content: $content, ...})
```

---

## Schemas (`app/schemas.py`)

```python
class IngestRequest(BaseModel):
    knowledge_base_id: str
    file_name: str
    # file đến qua multipart, không phải JSON body

class IngestResponse(BaseModel):
    document_id: str
    status: str          # 'done' | 'failed'
    total_chunks: int
    message: str | None

class AskRequest(BaseModel):
    knowledge_base_id: str
    session_id: str
    question: str

class Source(BaseModel):
    file_name: str
    page: int
    score: float
    preview: str

class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    session_id: str
    message_id: str
```

---

## Config (`.env.example`)

```env
# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Embedding (chạy local, không cần API)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384

# Qdrant Cloud
QDRANT_URL=https://xxx.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=...
QDRANT_COLLECTION=rag_chunks

# Neo4j AuraDB
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# RAG tuning
CHUNK_SIZE=600
CHUNK_OVERLAP=100
TOP_K=5

# Upload
UPLOAD_DIR=./uploads
```

---

## Ingest flow (chi tiết)

```python
# app/services/ingest.py — đây là logic cốt lõi cần viết

def ingest(kb_id: str, file_name: str, file_bytes: bytes) -> IngestResult:
    doc_id = str(uuid4())

    # 1. Lưu file
    save_pdf(file_bytes, doc_id)

    # 2. Parse
    pages = PdfParser().parse(file_bytes)
    # → [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}, ...]

    # 3. Chunk
    chunks = Chunker(CHUNK_SIZE, CHUNK_OVERLAP).chunk(pages, doc_id, kb_id, file_name)
    # → [Chunk(id, doc_id, kb_id, page, chunk_index, text), ...]

    # 4. Embed
    texts = [c.text for c in chunks]
    vectors = Embedder().embed(texts)
    # → list[list[float]]

    # 5. Upsert Qdrant
    QdrantStore().upsert(chunks, vectors)

    # 6. Lưu metadata Neo4j
    Neo4jStore().create_document(doc_id, kb_id, file_name, total_pages, total_chunks)

    return IngestResult(document_id=doc_id, total_chunks=len(chunks), status="done")
```

---

## Retrieval + Answer flow (chi tiết)

```python
# app/services/llm.py

def ask(kb_id: str, question: str) -> tuple[str, list[Source]]:
    # 1. Embed câu hỏi
    q_vector = Embedder().embed([question])[0]

    # 2. Tìm trong Qdrant, filter theo kb_id
    hits = QdrantStore().search(q_vector, kb_id, top_k=TOP_K)
    # → [{"text": ..., "file_name": ..., "page": ..., "score": ...}, ...]

    # 3. Build prompt
    context = "\n\n".join([
        f"[{h['file_name']} — trang {h['page']}]\n{h['text']}"
        for h in hits
    ])
    messages = [
        {"role": "system", "content": (
            "Bạn là trợ lý học tập. Chỉ dùng các đoạn tài liệu dưới đây để trả lời. "
            "Nếu không đủ thông tin, hãy nói rõ là tài liệu không đề cập. "
            "Không bịa thông tin ngoài tài liệu.\n\n"
            f"TÀI LIỆU:\n{context}"
        )},
        {"role": "user", "content": question}
    ]

    # 4. Gọi OpenAI
    response = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
    )
    answer = response.choices[0].message.content

    sources = [Source(file_name=h["file_name"], page=h["page"],
                      score=h["score"], preview=h["text"][:150])
               for h in hits]
    return answer, sources
```

---

## Testing

### Cấu trúc test

```
tests/
├── conftest.py       ← fixtures dùng chung
├── unit/             ← test từng hàm, không cần Qdrant/Neo4j thật
└── integration/      ← test với Qdrant Cloud + Neo4j AuraDB thật
```

### conftest.py

```python
import pytest
from app.config import Settings

@pytest.fixture(scope="session")
def settings():
    # Load từ .env.test (dùng KB test riêng, không đụng data thật)
    return Settings(_env_file=".env.test")

@pytest.fixture(scope="session")
def test_kb_id():
    # KB cố định chỉ dùng cho test, tạo 1 lần
    return "test-kb-fixed-uuid-001"

@pytest.fixture(scope="session")
def sample_pdf_path():
    return "sample_docs/test.pdf"

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(settings, test_kb_id):
    yield
    # Sau khi tất cả test xong → xóa data test khỏi Qdrant + Neo4j
    from app.services.qdrant_store import QdrantStore
    from app.services.neo4j_store import Neo4jStore
    QdrantStore(settings).delete_by_kb(test_kb_id)
    Neo4jStore(settings).delete_kb(test_kb_id)
```

### Unit tests (không cần kết nối cloud)

```python
# tests/unit/test_chunker.py
def test_chunk_basic():
    text = "A " * 700  # 700 words
    chunks = Chunker(chunk_size=600, overlap=100).chunk(
        pages=[{"page": 1, "text": text}],
        doc_id="d1", kb_id="kb1", file_name="test.pdf"
    )
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text.split()) <= 650

def test_chunk_preserves_page():
    pages = [{"page": 3, "text": "Nội dung trang 3"}]
    chunks = Chunker(600, 100).chunk(pages, "d1", "kb1", "f.pdf")
    assert all(c.page == 3 for c in chunks)

def test_chunk_short_text():
    # Văn bản ngắn không bị chunk
    pages = [{"page": 1, "text": "Ngắn"}]
    chunks = Chunker(600, 100).chunk(pages, "d1", "kb1", "f.pdf")
    assert len(chunks) == 1

# tests/unit/test_prompt_builder.py
def test_prompt_has_context():
    hits = [{"file_name": "a.pdf", "page": 1, "text": "Nội dung A", "score": 0.9}]
    msgs = build_messages("Câu hỏi?", hits)
    system_content = msgs[0]["content"]
    assert "a.pdf" in system_content
    assert "Nội dung A" in system_content

def test_prompt_no_hallucination_instruction():
    msgs = build_messages("?", [])
    assert "không bịa" in msgs[0]["content"].lower() or "không đề cập" in msgs[0]["content"].lower()
```

### Integration tests (kết nối Qdrant Cloud + Neo4j AuraDB thật)

```python
# tests/integration/test_ingest.py
def test_ingest_creates_chunks(settings, test_kb_id, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        result = ingest(kb_id=test_kb_id, file_name="test.pdf",
                        file_bytes=f.read(), settings=settings)

    assert result.status == "done"
    assert result.total_chunks > 0

    # Kiểm tra Qdrant có chunks
    qdrant = QdrantStore(settings)
    count = qdrant.count_by_kb(test_kb_id)
    assert count == result.total_chunks

    # Kiểm tra Neo4j có document node
    neo4j = Neo4jStore(settings)
    doc = neo4j.get_document(result.document_id)
    assert doc["status"] == "done"
    assert doc["total_chunks"] == result.total_chunks

# tests/integration/test_retrieval.py
def test_retrieval_returns_relevant_chunks(settings, test_kb_id):
    # Giả sử đã ingest từ test trước (dùng session scope)
    qdrant = QdrantStore(settings)
    hits = qdrant.search(
        query_vector=Embedder(settings).embed(["nội dung chính"])[0],
        kb_id=test_kb_id,
        top_k=3
    )
    assert len(hits) > 0
    assert all("file_name" in h for h in hits)
    assert all(0 <= h["score"] <= 1 for h in hits)

# tests/integration/test_chat.py
def test_ask_returns_answer(settings, test_kb_id):
    answer, sources = ask(
        kb_id=test_kb_id,
        question="Tài liệu này nói về gì?",
        settings=settings
    )
    assert isinstance(answer, str)
    assert len(answer) > 10
    assert len(sources) > 0
    assert all(s.score >= 0 for s in sources)

def test_ask_out_of_scope(settings, test_kb_id):
    answer, sources = ask(
        kb_id=test_kb_id,
        question="Công thức nấu phở bò là gì?",
        settings=settings
    )
    # Model nên nói không đủ thông tin, không bịa
    low_score = all(s.score < 0.5 for s in sources) if sources else True
    assert low_score or "không" in answer.lower() or "không đề cập" in answer.lower()
```

### Chạy test

```bash
# Chỉ chạy unit (không cần internet, không cần API key)
pytest tests/unit/ -v

# Chạy integration (cần .env.test có key thật)
pytest tests/integration/ -v

# Chạy tất cả + hiện coverage
pytest --cov=app --cov-report=term-missing

# Chạy 1 file cụ thể
pytest tests/integration/test_ingest.py -v -s
```

### `.env.test` — dùng riêng cho test

```env
# Dùng chung Qdrant/Neo4j cloud nhưng collection + KB riêng
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384
QDRANT_URL=https://xxx.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=...
QDRANT_COLLECTION=rag_chunks_test   ← collection RIÊNG để test không đụng data thật
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
```

---

## API Endpoints

```
POST /ingest
  Content-Type: multipart/form-data
  Body: file (PDF), knowledge_base_id (str)
  → IngestResponse

POST /ask
  Content-Type: application/json
  Body: AskRequest {knowledge_base_id, session_id, question}
  → AskResponse

GET  /health
  → {"status": "ok", "qdrant": "ok", "neo4j": "ok"}
```

---

## Thứ tự implement

```
Bước 1 — Setup cloud + skeleton
  - Tạo Qdrant Cloud cluster, tạo collection rag_chunks
  - Tạo Neo4j AuraDB instance
  - app/config.py, app/main.py, app/schemas.py
  - GET /health (kiểm tra kết nối cả 2 cloud)

Bước 2 — Services lõi
  - app/services/pdf_parser.py
  - app/services/chunker.py
  - app/services/embedder.py
  - Viết unit test ngay cho chunker + embedder

Bước 3 — Storage
  - app/services/qdrant_store.py  (upsert, search, delete_by_kb, count_by_kb)
  - app/services/neo4j_store.py   (create_document, get_document, delete_kb)

Bước 4 — Ingest endpoint
  - app/api/ingest.py
  - POST /ingest kết nối toàn bộ pipeline
  - Viết integration test_ingest.py

Bước 5 — Chat endpoint
  - app/services/llm.py
  - app/api/chat.py
  - POST /ask
  - Viết integration test_chat.py

Bước 6 — Kiểm tra thật
  - Upload 2-3 PDF liên quan (giáo trình, tài liệu nghiên cứu)
  - Hỏi câu hỏi in-scope và out-of-scope
  - Kiểm tra source attribution đúng file + trang
```

---

## requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-multipart==0.0.9
pydantic-settings==2.4.0
pypdf==5.1.0
sentence-transformers==3.2.1
openai==1.50.0
qdrant-client==1.11.3
neo4j==5.25.0
python-dotenv==1.0.1
pytest==8.3.3
pytest-cov==5.0.0
httpx==0.27.2          # test FastAPI endpoints
```

---

## Interface với team khác

RAG service chỉ expose 3 endpoints. Team frontend/backend khác cần biết:

```
Base URL: http://localhost:8000  (dev)  |  https://rag.your-domain.com  (prod)

POST /ingest
  Input:  multipart — field "file" (PDF), field "knowledge_base_id" (string)
  Output: {"document_id": "...", "status": "done", "total_chunks": 42}

POST /ask
  Input:  JSON — {"knowledge_base_id": "...", "session_id": "...", "question": "..."}
  Output: {
    "answer": "...",
    "sources": [{"file_name": "...", "page": 3, "score": 0.87, "preview": "..."}],
    "session_id": "...",
    "message_id": "..."
  }

GET /health
  Output: {"status": "ok", "qdrant": "ok", "neo4j": "ok"}
```

Session lưu trong Neo4j, team khác chỉ cần truyền `session_id` là đủ.
