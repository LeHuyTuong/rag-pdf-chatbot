# Kế hoạch nâng cấp RAG

Tài liệu này liệt kê các hạng mục cần làm để đưa hệ thống từ MVP hiện tại lên mức gần production. Các mục được xếp theo thứ tự **ROI (return on investment)** — làm từ trên xuống sẽ thấy chất lượng cải thiện rõ nhất với chi phí thấp nhất.

Mỗi hạng mục có:
- **Vấn đề** đang gặp
- **File / module** liên quan
- **Cách làm** đề xuất
- **Tiêu chí hoàn thành**

---

## P0 — Phải làm trước (ảnh hưởng trực tiếp đến chất lượng trả lời)

### 1. Đổi embedding model sang multilingual

**Vấn đề:** `sentence-transformers/all-MiniLM-L6-v2` được train chủ yếu trên dữ liệu tiếng Anh, recall trên tiếng Việt thấp ([`rag-api/app/config.py:19`](../rag-api/app/config.py#L19)).

**File liên quan:**
- `rag-api/app/config.py` — đổi `embedding_model_name`
- `rag-api/app/services/embedding_service.py` — verify dimension match
- `rag-api/app/services/qdrant_service.py` — collection cần được tạo lại với dimension mới
- `.env.example` — cập nhật biến môi trường

**Cách làm:**
1. Đổi sang `BAAI/bge-m3` (1024-dim, multilingual, hỗ trợ dense + sparse) hoặc `intfloat/multilingual-e5-large` (1024-dim, đơn giản hơn).
2. Thêm migration script ở `rag-api/scripts/reembed.py` để re-embed các document cũ và recreate Qdrant collection.
3. Bật cờ `EMBEDDING_DIM` trong config thay vì hardcode.

**Tiêu chí hoàn thành:**
- Recall@5 trên bộ eval tiếng Việt tăng ≥ 15% so với MiniLM.
- Re-ingest không lỗi với 5 PDF có sẵn.

---

### 2. Thêm cross-encoder reranker thật

**Vấn đề:** [`rag-api/app/services/reranking_service.py`](../rag-api/app/services/reranking_service.py) hiện chỉ là no-op, top-5 chunks vào LLM vẫn theo điểm hybrid thô — dễ kéo nhiễu.

**File liên quan:**
- `rag-api/app/services/reranking_service.py` — implement thật
- `rag-api/app/services/rag_pipeline.py` — đảm bảo rerank được gọi sau retrieval, trước khi cắt top-K
- `rag-api/requirements.txt` — thêm `sentence-transformers` (nếu chưa có)

**Cách làm:**
1. Dùng `BAAI/bge-reranker-v2-m3` (multilingual, lightweight).
2. Retrieval lấy `top_k_candidates = 20`, rerank xuống `MAX_CONTEXT_CHUNKS = 5`.
3. Lưu `rerank_score` vào `retrieval_report` để debug.
4. Có cờ `ENABLE_RERANKER=true|false` để có thể bypass khi test.

**Tiêu chí hoàn thành:**
- Faithfulness score (đo bằng RAGAS, xem mục #6) tăng ≥ 10%.
- Latency thêm < 500ms cho 20 chunks.

---

### 3. Conversation memory — condense câu hỏi follow-up

**Vấn đề:** Lịch sử chat được lưu MySQL nhưng không bơm vào query khi retrieve. Câu hỏi `"nó là gì?"` sau câu `"Lê Lợi là ai?"` sẽ retrieve sai hoàn toàn.

**File liên quan:**
- `rag-api/app/services/rag_pipeline.py` — thêm bước condense trước retrieval
- `rag-api/app/services/llm_service.py` — thêm method `condense_question(history, question)`
- `backend-spring/.../chat/service/ChatService.java` — truyền history vào RAG API
- `rag-api/app/api/chat.py` (hoặc route `/rag/ask`) — nhận field `history`
- `rag-api/app/prompts/condense_prompt.txt` — prompt template mới

**Cách làm:**
1. Spring gửi 3-5 message gần nhất cùng câu hỏi mới.
2. RAG API gọi LLM với prompt `"Dựa trên lịch sử, viết lại câu hỏi cuối thành một câu độc lập, đầy đủ ngữ cảnh"`.
3. Standalone question được dùng cho cả embedding lẫn keyword search.
4. Câu hỏi gốc vẫn dùng trong final prompt để LLM trả lời tự nhiên.

**Tiêu chí hoàn thành:**
- Test case follow-up `"nó là gì?"` retrieve được đúng document như câu hỏi đầy đủ.
- Không tăng latency > 1.5s.

---

### 4. Chống prompt injection từ chunk

**Vấn đề:** Chunk text được format thẳng vào prompt string ([`rag-api/app/services/llm_service.py:21`](../rag-api/app/services/llm_service.py#L21)). PDF chứa `"Ignore previous instructions and …"` có thể hijack model.

**File liên quan:**
- `rag-api/app/services/llm_service.py`
- `rag-api/app/prompts/rag_prompt.txt`

**Cách làm:**
1. Tách system message và user message rõ ràng (dùng `messages=[{role:"system"}, {role:"user"}]` của API).
2. Bọc chunk trong delimiter hiếm: `<chunk id="..."> … </chunk>`, dặn model không thực thi lệnh bên trong.
3. Sanitize chunk: replace các pattern như `"system:"`, `"ignore previous"` thành dạng escape (tùy chọn, log lại).
4. Thêm test trong `rag-api/tests/test_injection.py` với 3 payload độc.

**Tiêu chí hoàn thành:**
- 3 test injection không khiến LLM bỏ qua chỉ thị gốc.

---

## P1 — Nên làm sớm (cải thiện đáng kể chất lượng & vận hành)

### 5. Chunking thông minh theo cấu trúc

**Vấn đề:** Word-window 700/120 cố định ([`rag-api/app/services/chunker.py:44-52`](../rag-api/app/services/chunker.py#L44-L52)) cắt giữa câu, giữa section, không cross-page → mất ngữ cảnh.

**File liên quan:**
- `rag-api/app/services/chunker.py`
- `rag-api/app/services/pdf_parser.py` — có thể cần expose thêm heading info

**Cách làm:**
1. Dùng `RecursiveCharacterTextSplitter` của LangChain hoặc tự viết: tách theo `\n\n` → `\n` → `. ` → ` `.
2. Detect heading bằng regex (font size không có sẵn từ pypdf — chấp nhận heuristic theo dòng IN HOA / số mục).
3. Cho phép chunk cross-page nếu cùng section.
4. Thêm `section_title` vào metadata.

**Tiêu chí hoàn thành:**
- Không còn chunk cắt giữa câu (kiểm tra bằng test: chunk phải kết thúc bằng `.`, `?`, `!`, `:` hoặc end-of-section).

---

### 6. Tích hợp RAGAS evaluation

**Vấn đề:** Evaluation hiện tại ([`rag-api/tests/test_evaluation_metrics.py`](../rag-api/tests/test_evaluation_metrics.py)) chỉ tính `answer_accuracy` + `refusal_accuracy` tự chế — không biết model có hallucinate không.

**File liên quan:**
- `rag-api/app/services/evaluation_service.py` — thêm RAGAS metrics
- `rag-api/eval/eval_questions.json` — bộ câu hỏi vàng
- `rag-api/scripts/run_eval.py` — script CLI để chạy eval
- `rag-api/requirements.txt` — thêm `ragas`

**Cách làm:**
1. Tích hợp 4 metric chính của RAGAS: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.
2. Mỗi PR lớn chạy lại eval, log kết quả vào `docs/eval_results/YYYY-MM-DD.json`.
3. Nếu CI có ngân sách, tự động fail PR khi faithfulness giảm > 5%.

**Tiêu chí hoàn thành:**
- Chạy `python -m rag-api.scripts.run_eval` ra report đầy đủ 4 metric.
- Có baseline number cho main branch.

---

### 7. Async ingest qua job queue

**Vấn đề:** Upload PDF lớn block HTTP request, dễ timeout ([`README.md:186`](../README.md#L186)). User không có progress feedback.

**File liên quan:**
- `rag-api/app/api/documents.py` (hoặc route `/documents/ingest`)
- `rag-api/app/services/job_service.py` (mới)
- `backend-spring/.../document/service/DocumentService.java`
- `frontend/src/features/documents/hooks/useUploadDocument.js`
- `docker-compose.yml` — thêm Redis service

**Cách làm:**
1. Dùng `arq` (đơn giản, Redis-based, async-native cho FastAPI) thay vì Celery.
2. Endpoint `/documents/ingest` trả về `job_id` ngay; ingest chạy nền.
3. Endpoint mới `/documents/{id}/status` trả `pending|parsing|chunking|embedding|done|failed`.
4. Frontend poll status mỗi 2s, hiện progress bar.

**Tiêu chí hoàn thành:**
- PDF 200 trang upload không block UI > 2s.
- Status được cập nhật đúng qua từng bước.

---

### 8. Streaming response

**Vấn đề:** Câu trả lời dài (1000+ tokens) phải đợi LLM xong hết mới hiện. UX kém so với ChatGPT.

**File liên quan:**
- `rag-api/app/services/llm_service.py` — dùng `stream=True`
- `rag-api/app/api/chat.py` — endpoint SSE mới `/rag/ask/stream`
- `backend-spring/.../chat/controller/ChatController.java` — proxy SSE
- `frontend/src/features/chat/api/chatApi.js` — dùng `EventSource` thay vì `fetch`

**Cách làm:**
1. FastAPI `StreamingResponse` với `text/event-stream`.
2. Spring dùng `WebClient` reactive để forward stream.
3. Frontend append từng chunk vào message bubble.
4. Sources được gửi ở event cuối (`event: sources`).

**Tiêu chí hoàn thành:**
- Time-to-first-token < 1s.
- Stream không bị buffer ở Nginx (cần config `proxy_buffering off`).

---

## P2 — Có thời gian thì làm (nâng cao chất lượng & vận hành)

### 9. Multi-query / Query expansion

**Vấn đề:** Câu hỏi mơ hồ retrieve recall thấp. RAG hiện tại không có HyDE / multi-query.

**Cách làm:** Trước retrieval, gọi LLM sinh 3 paraphrase của câu hỏi → union kết quả retrieval → dedup → rerank. Có thể bật/tắt qua cờ `ENABLE_MULTI_QUERY`.

**Tiêu chí hoàn thành:** Recall@10 tăng ≥ 8% trên eval set.

---

### 10. BM25 thật cho hybrid search

**Vấn đề:** "Hybrid" hiện tại là vector + keyword scoring đơn giản ([`rag-api/app/services/retrieval_service.py:41`](../rag-api/app/services/retrieval_service.py#L41)), chưa phải BM25. `TODO.md:5` đã ghi nhận.

**Cách làm:** Dùng `rank_bm25` hoặc Elasticsearch nếu sẵn có. Hoặc tận dụng BGE-M3 sparse embedding (cùng model với mục #1 — tiện đôi đường).

**Tiêu chí hoàn thành:** Truy vấn keyword (tên riêng, số liệu) recall tăng rõ rệt so với pure vector.

---

### 11. Observability (logging, tracing, metrics)

**Vấn đề:** Logging có structured nhưng không có trace/metric exporter.

**File liên quan:**
- `rag-api/app/main.py` — thêm OpenTelemetry middleware
- `docker-compose.yml` — thêm Jaeger + Prometheus + Grafana

**Cách làm:**
1. Trace mỗi request: parse → chunk → embed → retrieve → rerank → LLM.
2. Metric: latency p50/p95/p99 cho từng bước, token usage, error rate.
3. Dashboard Grafana export ở `docs/grafana/`.

**Tiêu chí hoàn thành:** Mở Jaeger thấy được full trace của 1 câu hỏi.

---

### 12. Document deletion cleanup

**Vấn đề:** [`TODO.md:18`](../TODO.md#L18) — xóa document chưa cleanup Qdrant và storage.

**Cách làm:**
- Xóa points trong Qdrant theo `document_id` filter.
- Xóa file PDF gốc khỏi storage.
- Xóa row trong MySQL (chunks + document metadata).
- Wrap trong transaction / saga để consistency.

---

### 13. OCR cho PDF scan

**Vấn đề:** [`TODO.md:4`](../TODO.md#L4) — PDF scan trả warning, không extract được.

**Cách làm:** Tích hợp Tesseract (qua `pytesseract`) hoặc Google Document AI. Detect scan-only PDF → chạy OCR trước parse.

---

### 14. Multi-document chat

**Vấn đề:** [`TODO.md:7`](../TODO.md#L7) — không hỏi được qua nhiều PDF.

**Cách làm:** Bỏ filter `document_id` cứng trong retrieval, để user chọn scope (1 doc / 1 folder / all). Thêm filter UI ở chat panel.

---

## Quy trình áp dụng

1. Mỗi mục P0/P1 → tạo branch riêng, PR riêng, có eval trước/sau.
2. Sau mỗi mục, chạy lại `scripts/run_eval.py` (sau khi mục #6 xong) và update `docs/eval_results/`.
3. Cập nhật `TODO.md` (đánh dấu xong) và `docs/FLOW.md` (sửa flow nếu có thay đổi kiến trúc).
4. Không gộp nhiều mục vào 1 PR — khó review và khó rollback.

## Thứ tự ưu tiên đề xuất

```
Tuần 1-2: #1 (embedding) → #6 (RAGAS, cần có baseline)
Tuần 3:   #2 (reranker)  → đo improvement bằng RAGAS
Tuần 4:   #3 (condense)  → #4 (injection)
Tuần 5-6: #5 (chunking)  → #7 (async) → #8 (streaming)
Sau đó:   các mục P2 theo nhu cầu thực tế
```
