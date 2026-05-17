import json
import urllib.request

payload = {
    "file_path": "D:/Download/rag-chatbot-patched/rag-chatbot/storage/uploads/7bd63f35-a43d-4df7-b938-a24446080237_S_CH_PHONG_TH_Y__NG_D_NG.pdf",
    "document_id": "7bd63f35-a43d-4df7-b938-a24446080237",
    "user_id": "62432545-3e9e-486d-bf9e-6c48f2b82dd2",
    "file_name": "SÁCH PHONG THỦY ỨNG DỤNG.pdf",
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request('http://localhost:8000/documents/ingest', data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        print('STATUS', resp.status)
        print(resp.read().decode('utf-8'))
except Exception as e:
    print('ERROR', e)
