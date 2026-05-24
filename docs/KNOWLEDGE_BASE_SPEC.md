# Spec: Multi-PDF Knowledge Base (NotebookLM-style)

Tài liệu này mô tả đầy đủ thiết kế và các thay đổi cần thiết để nâng hệ thống từ
"chat với 1 PDF" lên "chat với nhiều PDF trong một Knowledge Base", tương tự NotebookLM.

---

## Mục tiêu

- User tạo được nhiều **Knowledge Base (KB)**, mỗi KB chứa 1–N file PDF.
- Chat với KB → LLM trả lời dựa trên nội dung **toàn bộ** PDF trong KB đó.
- User có thể upload thêm, xóa, đổi tên PDF trong KB bất kỳ lúc nào.
- Source attribution vẫn chỉ rõ câu trả lời đến từ **file nào, trang nào**.
- Chat session cũ (single-document) vẫn hoạt động bình thường (backward compat).

---

## Kiến trúc hiện tại (tham khảo)

```
Frontend (React)
    ↓ REST
Spring Boot (auth, session, document management)
    ↓ HTTP
Python FastAPI RAG API (ingest, retrieval, LLM)
    ↓
Qdrant (vector store)   MySQL (metadata, chunks, sessions)
```

**Điểm chốt cần thay đổi:**
- Qdrant search filter hiện là `user_id + document_id` → đổi thành `user_id + knowledge_base_id`
- `RagAskRequest` và `IngestRequest` hiện có trường `document_id` → thêm `knowledge_base_id`
- Spring `ChatSession` đang bind 1-1 với `document_id` → bind với `knowledge_base_id`

---

## 1. Data Layer

### 1.1 MySQL — Schema mới

```sql
-- Bảng mới: knowledge_bases
CREATE TABLE knowledge_bases (
    id          VARCHAR(36)  PRIMARY KEY,
    user_id     VARCHAR(36)  NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kb_user (user_id)
);

-- Bảng mới: knowledge_base_documents (linking table)
CREATE TABLE knowledge_base_documents (
    kb_id       VARCHAR(36) NOT NULL,
    document_id VARCHAR(36) NOT NULL,
    added_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (kb_id, document_id),
    INDEX idx_kbd_document (document_id)
);

-- Sửa bảng hiện tại: chat_sessions
ALTER TABLE chat_sessions
    ADD COLUMN knowledge_base_id VARCHAR(36) NULL,
    ADD INDEX idx_cs_kb (knowledge_base_id);
-- Giữ lại cột document_id để backward compat với session cũ
```

### 1.2 Qdrant — Payload field mới

Mỗi vector point (chunk) cần thêm field `knowledge_base_id`:

```python
# Payload cũ
{
    "chunk_id": "...",
    "document_id": "...",
    "user_id": "...",
    "file_name": "...",
    ...
}

# Payload mới — thêm field này
{
    "chunk_id": "...",
    "document_id": "...",      # GIỮ LẠI để source attribution
    "knowledge_base_id": "...", # MỚI
    "user_id": "...",
    "file_name": "...",
    ...
}
```

Field `knowledge_base_id` phải được index:

```python
# rag-api/app/services/qdrant_service.py — trong ensure_collection()
for field in ['user_id', 'document_id', 'knowledge_base_id', 'source_type', 'file_name']:
    client.create_payload_index(collection, field_name=field, field_schema='keyword')
```

### 1.3 Qdrant — Search filter mới

```python
# CŨ (rag-api/app/services/qdrant_service.py:124)
filters = qm.Filter(must=[
    qm.FieldCondition(key='user_id',     match=qm.MatchValue(value=user_id)),
    qm.FieldCondition(key='document_id', match=qm.MatchValue(value=document_id)),
])

# MỚI — search theo KB (tất cả documents trong KB)
filters = qm.Filter(must=[
    qm.FieldCondition(key='user_id',            match=qm.MatchValue(value=user_id)),
    qm.FieldCondition(key='knowledge_base_id',  match=qm.MatchValue(value=knowledge_base_id)),
])

# TÙY CHỌN — search theo 1 document cụ thể trong KB (mode "single doc")
filters = qm.Filter(must=[
    qm.FieldCondition(key='user_id',            match=qm.MatchValue(value=user_id)),
    qm.FieldCondition(key='knowledge_base_id',  match=qm.MatchValue(value=knowledge_base_id)),
    qm.FieldCondition(key='document_id',        match=qm.MatchValue(value=document_id)),
])
```

---

## 2. RAG API (Python / FastAPI)

### 2.1 Schema thay đổi

```python
# rag-api/app/models/schemas.py

class IngestRequest(BaseModel):
    user_id:           str
    document_id:       str
    knowledge_base_id: str          # MỚI — bắt buộc
    file_path:         str
    file_name:         str

class RagAskRequest(BaseModel):
    user_id:           str
    knowledge_base_id: str          # MỚI — thay document_id
    document_id:       str | None = None  # TÙY CHỌN — scope về 1 doc
    session_id:        str
    message_id:        str
    question:          str
```

### 2.2 Ingest pipeline

```python
# rag-api/app/pipelines/ingest_pipeline.py
# Thêm knowledge_base_id vào từng chunk khi upsert vào Qdrant

chunk.knowledge_base_id = request.knowledge_base_id  # set trước khi upsert
```

### 2.3 Retrieval service

```python
# rag-api/app/services/retrieval_service.py

def retrieve(
    self,
    user_id: str,
    knowledge_base_id: str,
    question: str,
    document_id: str | None = None,  # None = search toàn KB
) -> list[RetrievedChunk]:
    hits = self.qdrant.search(user_id, knowledge_base_id, question, self.settings.top_k, document_id)
    ...
```

### 2.4 Endpoint mới — Knowledge Base CRUD

```
POST   /knowledge-bases              Tạo KB mới
GET    /knowledge-bases              List KB của user
GET    /knowledge-bases/{kb_id}      Chi tiết KB + danh sách docs
PUT    /knowledge-bases/{kb_id}      Đổi tên / description
DELETE /knowledge-bases/{kb_id}      Xóa KB (và cleanup chunks trong Qdrant)

POST   /knowledge-bases/{kb_id}/documents/{doc_id}   Thêm doc vào KB
DELETE /knowledge-bases/{kb_id}/documents/{doc_id}   Xóa doc khỏi KB
                                                      (xóa chunks Qdrant theo document_id + kb_id)
```

### 2.5 Xóa document khỏi KB — logic cleanup

Khi xóa document khỏi KB, cần xóa các Qdrant points của document đó **trong KB đó**:

```python
# Xóa points trong Qdrant với filter kép
client.delete(
    collection_name=collection,
    points_selector=qm.FilterSelector(filter=qm.Filter(must=[
        qm.FieldCondition(key='document_id',       match=qm.MatchValue(value=document_id)),
        qm.FieldCondition(key='knowledge_base_id', match=qm.MatchValue(value=kb_id)),
    ]))
)
# Sau đó xóa row trong knowledge_base_documents
```

Lưu ý: 1 document có thể tồn tại trong nhiều KB. Chỉ xóa Qdrant points của cặp (document_id, kb_id)
cụ thể, không xóa document gốc.

---

## 3. Spring Boot Backend

### 3.1 Entity mới

```java
// KnowledgeBase.java
@Entity
@Table(name = "knowledge_bases")
public class KnowledgeBase {
    @Id private String id;          // UUID
    private String userId;
    private String name;
    private String description;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}

// KnowledgeBaseDocument.java (linking entity)
@Entity
@Table(name = "knowledge_base_documents")
public class KnowledgeBaseDocument {
    @EmbeddedId private KnowledgeBaseDocumentId id; // (kbId, documentId)
    private LocalDateTime addedAt;
}
```

### 3.2 Sửa ChatSession entity

```java
// ChatSession.java — thêm field
private String knowledgeBaseId;   // MỚI
// Giữ lại documentId cho session cũ (nullable)
```

### 3.3 Controller mới

```
POST   /api/knowledge-bases
GET    /api/knowledge-bases
GET    /api/knowledge-bases/{kbId}
PUT    /api/knowledge-bases/{kbId}
DELETE /api/knowledge-bases/{kbId}

POST   /api/knowledge-bases/{kbId}/documents
DELETE /api/knowledge-bases/{kbId}/documents/{docId}
```

### 3.4 Sửa ChatService

```java
// ChatService.java — ask() nhận knowledgeBaseId
RagAskRequest ragRequest = RagAskRequest.builder()
    .userId(userId)
    .knowledgeBaseId(session.getKnowledgeBaseId())  // MỚI
    .documentId(request.getDocumentId())             // optional scope
    .sessionId(sessionId)
    .messageId(messageId)
    .question(request.getQuestion())
    .build();
```

---

## 4. Frontend (React)

### 4.1 Component mới

**`KnowledgeBaseManager`** — trang quản lý KB
- List KB của user
- Tạo KB mới (nhập tên)
- Xóa KB
- Xem và quản lý PDF trong KB: upload thêm, xóa từng file
- Drag-and-drop PDF vào KB

**`KnowledgeBaseSelector`** — dropdown chọn KB trước khi chat
- Hiển thị tên KB + số lượng PDF
- Cho phép tạo KB mới ngay từ đây

### 4.2 Sửa component hiện có

**`ChatBox`** — sửa source display
```
Trước: "Nguồn: trang 3-5"
Sau:   "Nguồn: [tên_file.pdf] • trang 3-5"
```
Vì giờ nhiều PDF, cần luôn hiển thị tên file.

**`Sidebar`** — thêm KB selector phía trên danh sách chat

**`ChatSession` context** — thêm `selectedKnowledgeBaseId` vào state

### 4.3 Flow upload mới

```
User mở KnowledgeBaseManager
→ Chọn hoặc tạo KB
→ Upload PDF(s)
→ Mỗi PDF gọi POST /api/documents/upload (Spring)
→ Spring gọi POST /documents/ingest (RAG API) với knowledge_base_id
→ RAG API ingest và lưu chunks với knowledge_base_id
→ UI hiện trạng thái ingest từng file
```

---

## 5. Migration Data Cũ

Script chạy 1 lần khi deploy:

```sql
-- Tạo 1 KB mặc định cho mỗi user
INSERT INTO knowledge_bases (id, user_id, name, description, created_at, updated_at)
SELECT
    UUID()     AS id,
    user_id    AS user_id,
    'My Documents' AS name,
    'Automatically created from existing documents' AS description,
    NOW(), NOW()
FROM (SELECT DISTINCT user_id FROM documents) u;

-- Gán tất cả document hiện tại vào KB mặc định của user đó
INSERT INTO knowledge_base_documents (kb_id, document_id, added_at)
SELECT kb.id, d.id, NOW()
FROM documents d
JOIN knowledge_bases kb ON kb.user_id = d.user_id AND kb.name = 'My Documents';

-- Cập nhật chat_sessions cũ
UPDATE chat_sessions cs
JOIN documents d ON d.id = cs.document_id
JOIN knowledge_bases kb ON kb.user_id = d.user_id AND kb.name = 'My Documents'
SET cs.knowledge_base_id = kb.id
WHERE cs.knowledge_base_id IS NULL;
```

**Re-ingest Qdrant** (cần chạy script riêng):
Các chunks trong Qdrant hiện **chưa có field `knowledge_base_id`** trong payload.
Phải re-embed hoặc chạy script update payload từng point theo `document_id → kb_id mapping`.

```python
# scripts/migrate_qdrant_kb.py
# Với mỗi document_id → lấy kb_id từ MySQL → Qdrant set_payload() cho các points đó
client.set_payload(
    collection_name=collection,
    payload={"knowledge_base_id": kb_id},
    points=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))])
)
```

---

## 6. Thứ tự implement

```
Bước 1 — MySQL migration
  - Tạo bảng knowledge_bases, knowledge_base_documents
  - Alter chat_sessions
  - Chạy data migration script

Bước 2 — Qdrant migration
  - Thêm knowledge_base_id vào ensure_collection() payload index
  - Chạy migrate_qdrant_kb.py để backfill payload cũ

Bước 3 — RAG API
  - Sửa IngestRequest / RagAskRequest schema
  - Sửa QdrantService.search() filter
  - Sửa IngestPipeline để set knowledge_base_id trên chunk
  - Sửa RetrievalService.retrieve() signature
  - Thêm /knowledge-bases/* endpoints
  - Test: ingest 2 PDF vào cùng KB → query xuyên cả 2

Bước 4 — Spring Backend
  - Thêm entity KnowledgeBase, KnowledgeBaseDocument
  - Thêm KnowledgeBaseController, KnowledgeBaseService
  - Sửa ChatService.ask() → dùng knowledgeBaseId
  - Sửa ChatSession entity

Bước 5 — Frontend
  - KnowledgeBaseManager page
  - KnowledgeBaseSelector component
  - Sửa ChatBox source display
  - Sửa Sidebar
  - Kết nối API mới

Bước 6 — Testing
  - Upload 3 PDF vào 1 KB, hỏi câu hỏi cross-document → source phải từ đúng file
  - Xóa 1 PDF → câu hỏi liên quan file đó không còn trả lời được
  - Session cũ (single-doc) vẫn hoạt động
```

---

## 7. Điểm cần chú ý khi implement

**Source attribution** — luôn giữ `document_id` trong mọi chunk kể cả sau migration.
Khi trả lời, source phải có `file_name` để user biết thông tin đến từ file nào.

**Xóa document vs xóa KB** — phân biệt rõ:
- Xóa doc khỏi KB: xóa Qdrant points + linking row, không xóa file gốc (vì doc có thể có trong KB khác).
- Xóa KB: xóa tất cả Qdrant points có `knowledge_base_id` đó + xóa tất cả linking rows + xóa KB row.
- Xóa file hoàn toàn: chỉ khi xóa khỏi tất cả KB và bảng `documents`.

**Concurrent KB** — 1 document có thể thuộc nhiều KB (như Google Drive). Thiết kế trên hỗ trợ điều này.

**Scoring với nhiều PDF** — khi search xuyên 5–15 PDF, top_k nên tăng lên (ví dụ 20 thay vì 10)
và reranker quan trọng hơn để lọc nhiễu cross-document.

**Empty KB** — KB không có PDF trả về lỗi rõ ràng thay vì answer kiểu "không tìm thấy".

---

## 8. API Contract tóm tắt

### Knowledge Base

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/knowledge-bases` | `{name, description?}` | KnowledgeBase |
| GET | `/api/knowledge-bases` | — | `KnowledgeBase[]` |
| GET | `/api/knowledge-bases/:id` | — | `KnowledgeBase + documents[]` |
| PUT | `/api/knowledge-bases/:id` | `{name?, description?}` | KnowledgeBase |
| DELETE | `/api/knowledge-bases/:id` | — | 204 |
| POST | `/api/knowledge-bases/:id/documents` | `{documentId}` | 201 |
| DELETE | `/api/knowledge-bases/:id/documents/:docId` | — | 204 |

### Chat (sửa)

| Method | Path | Body cũ | Body mới |
|--------|------|---------|---------|
| POST | `/api/chat/sessions` | `{documentId, title}` | `{knowledgeBaseId, title, documentId?}` |
| POST | `/api/chat/sessions/:id/messages` | `{question}` | `{question, documentId?}` (scope optional) |

### RAG API (internal)

| Method | Path | Thay đổi |
|--------|------|---------|
| POST | `/documents/ingest` | Thêm `knowledge_base_id` vào request |
| POST | `/rag/ask` | Đổi `document_id` → `knowledge_base_id`; `document_id` optional |
| POST | `/knowledge-bases` | Endpoint mới |
| GET | `/knowledge-bases` | Endpoint mới |
| DELETE | `/knowledge-bases/:kb_id/documents/:doc_id` | Endpoint mới |
