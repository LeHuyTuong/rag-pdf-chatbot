import json
from pathlib import Path
import requests
from app.services.evaluation_service import EvaluationService

BASE_URL = 'http://localhost:8000'
ROOT = Path(__file__).resolve().parent
items = json.loads((ROOT / 'eval_questions.json').read_text(encoding='utf-8'))
responses = []
for item in items:
    payload = {
        'user_id': item.get('user_id', 'user_001'),
        'document_id': item.get('document_id', 'doc_001'),
        'session_id': 'eval_session',
        'message_id': item['id'],
        'question': item['question'],
    }
    try:
        responses.append(requests.post(f'{BASE_URL}/rag/ask', json=payload, timeout=30).json())
    except Exception as error:
        responses.append({'answer': '', 'confidence': 0, 'sources': [], 'error': str(error)})
report = EvaluationService().evaluate_items(items, responses, ROOT / 'reports')
print(json.dumps(report, ensure_ascii=False, indent=2))
