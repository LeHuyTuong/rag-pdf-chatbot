import json
import logging
import re
import time
from collections.abc import Callable

import requests
from openai import OpenAI
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.graph.graph_schema import GraphChunk, GraphEntity, GraphExtractionResult, GraphRelation, normalize_entity_name

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = '''Bạn là hệ thống trích xuất knowledge graph từ tài liệu lịch sử Việt Nam.

Chỉ dựa vào CHUNK_TEXT.
Không dùng kiến thức ngoài.
Không bịa entity.
Không bịa quan hệ.
Không trích xuất câu hỏi kiểm tra hoặc mục tham khảo không cung cấp sự kiện rõ ràng.
Nếu không có thông tin rõ ràng, trả về arrays rỗng.

Return JSON only:
{{
  "entities": [
    {{
      "name": "...",
      "type": "PERSON|EVENT|ORG|PLACE|CONCEPT|POLICY|PERIOD|IMPACT|ACTION",
      "description": "...",
      "confidence": 0.0
    }}
  ],
  "relations": [
    {{
      "source": "...",
      "target": "...",
      "relation_type": "RELATE_TO",
      "description": "...",
      "confidence": 0.0
    }}
  ]
}}

CHUNK_TEXT:
{chunk_text}
'''


class GraphExtractor:
    def __init__(
        self,
        settings: Settings | None = None,
        model_call: Callable[[str], str] | None = None,
    ):
        self.settings = settings or get_settings()
        self.model_call = model_call or self._call_model
        self.last_error: str | None = None

    def extract(self, chunk: GraphChunk) -> GraphExtractionResult:
        self.last_error = None
        if not chunk.text.strip():
            return GraphExtractionResult()
        prompt = EXTRACTION_PROMPT.format(chunk_text=chunk.text[:12000])
        for attempt in range(2):
            try:
                return self.parse_json(self.model_call(prompt), chunk)
            except (ValueError, json.JSONDecodeError, ValidationError) as error:
                self.last_error = f'invalid_json: {error.__class__.__name__}'
                logger.warning('graph extraction JSON parse failed chunk_id=%s attempt=%s', chunk.chunk_id, attempt + 1)
            except Exception as error:
                self.last_error = f'model_error: {error.__class__.__name__}'
                logger.error('graph extraction model call failed chunk_id=%s attempt=%s type=%s', chunk.chunk_id, attempt + 1, error.__class__.__name__)
            if attempt == 0:
                continue
        return GraphExtractionResult()

    @staticmethod
    def parse_json(response_text: str, chunk: GraphChunk) -> GraphExtractionResult:
        text = (response_text or '').strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*```$', '', text)
        start = text.find('{')
        end = text.rfind('}')
        if start < 0 or end < start:
            raise ValueError('LLM response has no JSON object')
        payload = json.loads(text[start:end + 1])

        entities: dict[tuple[str, str], GraphEntity] = {}
        for raw in payload.get('entities', []):
            try:
                entity = GraphEntity(
                    name=str(raw['name']),
                    type=str(raw['type']).upper(),
                    description=raw.get('description'),
                    confidence=raw.get('confidence'),
                )
            except (KeyError, ValidationError, ValueError):
                continue
            entities.setdefault((entity.normalized_name, entity.type), entity)

        relations = []
        seen_relations = set()
        by_name = {entity.normalized_name: entity for entity in entities.values()}
        for raw in payload.get('relations', []):
            source = by_name.get(normalize_entity_name(str(raw.get('source', ''))))
            target = by_name.get(normalize_entity_name(str(raw.get('target', ''))))
            if not source or not target or str(raw.get('relation_type', '')).upper() != 'RELATE_TO':
                continue
            try:
                relation = GraphRelation(
                    source_entity=source,
                    target_entity=target,
                    relation_type='RELATE_TO',
                    description=str(raw.get('description') or ''),
                    confidence=raw.get('confidence'),
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    file_name=chunk.file_name,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                )
            except (ValidationError, ValueError):
                continue
            key = (source.entity_key, target.entity_key, relation.description, chunk.chunk_id)
            if key not in seen_relations:
                relations.append(relation)
                seen_relations.add(key)
        return GraphExtractionResult(entities=list(entities.values()), relations=relations)

    def _call_model(self, prompt: str) -> str:
        if self._use_google_native_api():
            return self._call_google(prompt)
        api_key = self.settings.llm_api_key or self.settings.openai_api_key
        if not api_key and not self.settings.llm_base_url:
            raise RuntimeError('No LLM configuration is available for graph extraction')
        client = OpenAI(api_key=api_key or 'local-model', base_url=self.settings.llm_base_url)
        response = client.chat.completions.create(
            model=self.settings.llm_model or self.settings.openai_model,
            temperature=0.0,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return response.choices[0].message.content or ''

    def _use_google_native_api(self) -> bool:
        provider = self.settings.llm_provider.lower()
        base_url = self.settings.llm_base_url or ''
        return provider in {'google', 'google_ai', 'gemini'} or 'generativelanguage.googleapis.com' in base_url

    def _call_google(self, prompt: str) -> str:
        if not self.settings.llm_api_key:
            raise RuntimeError('LLM_API_KEY is required for Google graph extraction')
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.0},
        }
        errors = []
        model_names = [self.settings.llm_model or self.settings.openai_model]
        if self.settings.llm_fallback_model and self.settings.llm_fallback_model not in model_names:
            model_names.append(self.settings.llm_fallback_model)
        for model_name in model_names:
            response = self._post_google(model_name, payload)
            if response.status_code < 400:
                parts = response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
                return ''.join(part.get('text', '') for part in parts if not part.get('thought')).strip()
            errors.append(f'{model_name}: HTTP {response.status_code}')
        raise RuntimeError('Google graph extraction failed (' + '; '.join(errors) + ')')

    def _post_google(self, model_name: str, payload: dict) -> requests.Response:
        response = None
        for attempt in range(5):
            try:
                response = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent',
                    params={'key': self.settings.llm_api_key},
                    json=payload,
                    timeout=90,
                )
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(min(30, 2 ** attempt))
                continue
            if response.status_code not in {429, 500, 503}:
                return response
            if attempt < 4:
                time.sleep(min(30, 2 ** attempt))
        assert response is not None
        return response
