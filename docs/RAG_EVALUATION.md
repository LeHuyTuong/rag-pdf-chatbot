# RAG Evaluation

## Mục đích

`rag-api/scripts/batch_eval_history_rag.py` chạy batch câu hỏi kiểm thử cho tài liệu “Lịch sử Việt Nam tập 15 Từ năm 1986 đến năm 2000”.

Script gửi câu hỏi qua RAG API, không gọi trực tiếp LLM, không tự tạo đáp án mẫu và không fake kết quả nếu API chưa chạy. Kết quả được lưu để đọc thủ công và tính metric:

- TXT: report dễ đọc, có answer, source và auto checks.
- CSV: bảng gọn để tính thống kê.
- JSONL: record đầy đủ để debug.

Batch gồm nhóm câu hỏi đúng tài liệu 1986–2000 và nhóm bẫy Đinh Bộ Lĩnh. Với nhóm bẫy, câu trả lời tốt là từ chối có kiểm soát nếu tài liệu hiện tại không chứa lịch sử thời Đinh.

## Start RAG API

Từ thư mục `rag-api`:

```bash
uvicorn app.main:app --reload --port 8001
```

Kiểm tra nhanh:

```bash
curl http://localhost:8001/health
```

## Chạy Batch Eval

Từ thư mục `rag-api`:

```bash
python scripts/batch_eval_history_rag.py
```

Mặc định script dùng:

```bash
RAG_API_URL=http://localhost:8001
EVAL_MAX_RETRIES=3
EVAL_TIMEOUT_SECONDS=120
EVAL_PER_QUESTION_TIMEOUT_SECONDS=90
EVAL_REQUEST_DELAY_SECONDS=3
EVAL_STOP_ON_RATE_LIMIT=false
EVAL_RESUME=false
```

Nếu cần chỉ định tài liệu/người dùng:

```bash
RAG_API_URL=http://localhost:8001
SMOKE_DOCUMENT_ID=<document-id>
SMOKE_USER_ID=<user-id>
python scripts/batch_eval_history_rag.py
```

## Rate Limit Và Resume

Script không gửi toàn bộ câu hỏi liên tục. Mặc định có delay 3 giây giữa các câu và có retry với exponential backoff cho HTTP `429`, `500`, `502`, `503`, `504` và timeout/kết nối lỗi.

`EVAL_TIMEOUT_SECONDS` áp dụng cho từng HTTP request đến RAG API. `EVAL_PER_QUESTION_TIMEOUT_SECONDS` là hard timeout cho toàn bộ một câu hỏi, bao gồm retry/backoff; nếu vượt ngưỡng này, script ghi `verdict=ERROR` cho `question_id` đó và đi tiếp câu sau.

Với free/limited APIs, nên dùng delay 5–10 giây:

```bash
EVAL_REQUEST_DELAY_SECONDS=10
EVAL_MAX_RETRIES=3
EVAL_TIMEOUT_SECONDS=120
EVAL_PER_QUESTION_TIMEOUT_SECONDS=90
python scripts/batch_eval_history_rag.py
```

Với local model, delay có thể là 0–1 giây:

```bash
EVAL_REQUEST_DELAY_SECONDS=1
python scripts/batch_eval_history_rag.py
```

Nếu gặp HTTP `429`, hãy tăng `EVAL_REQUEST_DELAY_SECONDS`. Khi API trả `Retry-After`, script sẽ tôn trọng header đó. Nếu không có `Retry-After`, script đợi lần lượt 30s, 60s, 120s trước các lần retry 429.

Nếu muốn dừng ngay khi gặp rate limit:

```bash
EVAL_STOP_ON_RATE_LIMIT=true
python scripts/batch_eval_history_rag.py
```

Nếu batch bị dừng giữa chừng, bật resume để dùng file JSONL mới nhất trong `rag-api/storage/eval/` và bỏ qua các `question_id` đã có:

```bash
EVAL_RESUME=true
python scripts/batch_eval_history_rag.py
```

Nếu không set `SMOKE_DOCUMENT_ID`, script sẽ reuse logic smoke test để tìm document mới nhất trong MySQL. Nếu không tìm được document, script dừng với lỗi:

```text
Cannot run batch evaluation: missing documentId. Set SMOKE_DOCUMENT_ID or ingest/select a document first.
```

## Output

Output nằm trong:

```text
rag-api/storage/eval/
```

Tên file có timestamp:

```text
rag_eval_history_YYYYMMDD_HHMMSS.txt
rag_eval_history_YYYYMMDD_HHMMSS.csv
rag_eval_history_YYYYMMDD_HHMMSS.jsonl
```

## Metric Từ CSV

Các metric nên tính:

- `total_questions`: tổng số dòng câu hỏi.
- `pass_rate`: `(PASS + PASS_TRAP_REFUSAL) / total_questions`.
- `source_coverage`: số câu có `has_sources=true` / `total_questions`.
- `trap_pass_rate`: số câu trap có `trap_passed=true` / số câu trap.
- `hallucination_risk_count`: số dòng có `hallucination_risk=true`.
- `vietnamese_diacritics_pass_rate`: số câu có `vietnamese_diacritics_ok=true` / `total_questions`.
- `avg_latency_ms`: trung bình cột `latency_ms`.

## Lưu Ý Khi Chấm

Auto checks chỉ là heuristic. Hãy dùng TXT để đọc lại các câu `WARNING`, `FAIL`, `PASS_TRAP_REFUSAL` và `FAIL_HALLUCINATION_RISK`.

Nếu câu bẫy Đinh Bộ Lĩnh bị trả lời chi tiết mà không có từ chối có kiểm soát, cần xem là rủi ro hallucination, kể cả khi câu trả lời nghe đúng theo kiến thức phổ thông.

## Recommended Run-Control Commands

Quick 2-question check:

```powershell
cd rag-api
$env:EVAL_REQUEST_DELAY_SECONDS="6"
python scripts\batch_eval_history_rag.py --groups Q --limit 2 --run-id quick-check
```

Quick 10-question test:

```powershell
python scripts\batch_eval_history_rag.py --groups Q --run-id quick-001 --resume
```

Trap-only test:

```powershell
python scripts\batch_eval_history_rag.py --groups E --run-id trap-001 --resume
```

Full safe eval:

```powershell
$env:EVAL_REQUEST_DELAY_SECONDS="8"
$env:EVAL_TIMEOUT_SECONDS="180"
$env:EVAL_PER_QUESTION_TIMEOUT_SECONDS="210"
python scripts\batch_eval_history_rag.py --groups A,B,C,D,E,Q --run-id full-001 --resume
```

Resume interrupted full run:

```powershell
python scripts\batch_eval_history_rag.py --run-id full-001 --resume
```

Regenerate reports from JSONL without calling the RAG API:

```powershell
python scripts\batch_eval_history_rag.py --from-jsonl storage\eval\rag_eval_history_full-001.jsonl
```

Run-control flags:

- `--run-id`: writes `rag_eval_history_<run-id>.jsonl/.csv/.txt`.
- `--groups`: comma-separated groups, for example `Q`, `E`, or `A,B,C`.
- `--limit`: caps the selected question count after group filtering.
- `--start-from`: skips selected questions until the given `question_id`.
- `--from-jsonl`: regenerates TXT/CSV from an existing JSONL checkpoint and never calls the RAG API.
- `--resume`: skips `question_id` values already present in the JSONL checkpoint. With `--run-id`, resume uses the matching run-id file instead of the latest JSONL.
- `--retry-errors`: with `--resume`, re-runs records whose current `verdict` is `ERROR`.
