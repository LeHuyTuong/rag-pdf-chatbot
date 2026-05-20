# Local Runbook

Use this when you need to restart services after code changes and verify the RAG chatbot in the browser.

## 1. Stop Old Local Services

PowerShell:

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in 3000,5173,8001,8080 } |
  Select-Object LocalPort,OwningProcess

Stop-Process -Id <PID> -Force
```

Only stop PIDs that belong to this repo's frontend, backend, or RAG API.

## 2. Start RAG API With Current Code

```powershell
cd rag-api
$env:MAX_CONTEXT_CHUNKS = "5"
$env:TOP_K = "12"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

If `.env` still has `MAX_CONTEXT_CHUNKS=3`, the environment variable above overrides it for this session.

## 3. Start Spring Backend

```powershell
cd backend-spring
.\mvnw.cmd spring-boot:run
```

If port `8080` is busy, stop the old backend process first.

## 4. Start Frontend

```powershell
npm --prefix frontend run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## 5. Fast Automated Checks

Backend:

```powershell
cd backend-spring
.\mvnw.cmd test
```

RAG API:

```powershell
cd rag-api
python -m pytest tests
$env:SMOKE_USER_ID = "<user id that owns the document>"
$env:SMOKE_DOCUMENT_ID = "<document id>"
python scripts/smoke_rag_quality.py
```

Frontend:

```powershell
npm --prefix frontend run test:chat-order
npm --prefix frontend run build
```

## 6. Browser Manual Verification

1. Select the Vietnamese PDF document.
2. Send three questions in a row.
3. Confirm the visible order stays: old user, old assistant, new user, new assistant.
4. Refresh the page and confirm history remains `createdAt ASC`.
5. Ask `Nội dung chính của tài liệu này là gì?` and confirm the answer has Vietnamese diacritics.
6. Ask `Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?`.
7. Open Retrieval/Answer reports and confirm top chunks include relevant content about Đại hội VI, sai lầm/khuyết điểm, khủng hoảng, and cơ chế quản lý quan liêu/bao cấp.
8. Confirm sources show file name, page, and chunk.

## 7. Re-ingestion Decision

Re-ingestion is required only when retrieval previews show accent-stripped or old damaged payloads. If so:

1. Stop services writing to Qdrant.
2. Delete the old Qdrant collection or local Qdrant folder.
3. Start Qdrant/RAG API.
4. Upload or ingest the PDF again.
5. Re-run `python scripts/smoke_rag_quality.py`.
