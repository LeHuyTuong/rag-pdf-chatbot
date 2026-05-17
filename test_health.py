import urllib.request, json, os

print('=== Test: RAG API health ===')
r = urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3)
print(f'OK: {r.read().decode()}')

print()
print('=== Test: Backend Spring Boot health ===')
r = urllib.request.urlopen('http://localhost:8080/actuator/health', timeout=3)
print(f'OK: {r.read().decode()}')

print()
print('=== Test: RAG API ingest with real PDF ===')
uploads_dir = 'storage/uploads'
pdfs = [f for f in os.listdir(uploads_dir) if f.endswith('.pdf') and os.path.getsize(os.path.join(uploads_dir, f)) > 100]
if pdfs:
    pdf_path = os.path.join(uploads_dir, pdfs[0])
    pdf_name = pdfs[0]
    print(f'Using: {pdf_name} ({os.path.getsize(pdf_path)} bytes)')
    
    data = json.dumps({
        'user_id': '00000000-0000-0000-0000-000000000001',
        'document_id': '00000000-0000-0000-0000-000000000002',
        'file_path': pdf_path.replace('\\', '/'),
        'file_name': pdf_name
    }).encode()
    
    req = urllib.request.Request(
        'http://127.0.0.1:8001/documents/ingest',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    r = urllib.request.urlopen(req, timeout=30)
    result = json.loads(r.read().decode())
    print(f'Status: {result.get("status")}')
    print(f'Pages: {result.get("total_pages")}')
    print(f'Chunks: {result.get("total_chunks")}')
    print(f'Parser: {result.get("parser_used")}')
else:
    print('No PDFs found')