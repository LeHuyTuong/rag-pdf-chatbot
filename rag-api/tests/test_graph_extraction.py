from app.graph.graph_extractor import GraphExtractor
from app.graph.graph_schema import GraphChunk, GraphEntity, normalize_entity_name


def chunk() -> GraphChunk:
    return GraphChunk(
        chunk_id='chunk-1',
        document_id='document-1',
        file_name='lich-su.pdf',
        page_number=12,
        chunk_index=3,
        text='Đại hội VI liên quan đến công cuộc Đổi mới.',
    )


def test_normalization_keeps_vietnamese_diacritics():
    assert normalize_entity_name('  Đại   hội VI ') == 'đại hội vi'
    assert GraphEntity(name='Đổi mới', type='CONCEPT').normalized_name == 'đổi mới'


def test_graph_extractor_handles_valid_json_and_adds_chunk_provenance():
    extractor = GraphExtractor(
        model_call=lambda _prompt: '''
        ```json
        {
          "entities": [
            {"name": "Đại hội VI", "type": "EVENT", "description": "Sự kiện", "confidence": 0.9},
            {"name": "Đổi mới", "type": "CONCEPT", "description": "Công cuộc", "confidence": 0.9}
          ],
          "relations": [
            {"source": "Đại hội VI", "target": "Đổi mới", "relation_type": "RELATE_TO",
             "description": "mở đầu công cuộc", "confidence": 0.8}
          ]
        }
        ```
        ''',
    )

    result = extractor.extract(chunk())

    assert len(result.entities) == 2
    assert len(result.relations) == 1
    assert result.relations[0].chunk_id == 'chunk-1'
    assert result.relations[0].document_id == 'document-1'
    assert result.relations[0].file_name == 'lich-su.pdf'


def test_graph_extractor_handles_invalid_json_gracefully_after_retry():
    calls = []

    def invalid_call(_prompt: str) -> str:
        calls.append(1)
        return 'not-json'

    extractor = GraphExtractor(model_call=invalid_call)
    result = extractor.extract(chunk())

    assert len(calls) == 2
    assert result.entities == []
    assert result.relations == []
    assert extractor.last_error is not None
