import re

from app.graph.graph_schema import GraphEvidence, normalize_entity_name
from app.graph.neo4j_client import Neo4jClient


class GraphRetriever:
    STOP_WORDS = {
        'ai', 'là', 'gì', 'có', 'nào', 'như', 'thế', 'với', 'đến', 'sau',
        'liên', 'quan', 'công', 'cuộc', 'việt', 'nam', 'thay', 'đổi',
    }

    def __init__(self, client: Neo4jClient):
        self.client = client

    def retrieve(
        self,
        question: str,
        document_id: str | None = None,
        top_k: int = 10,
    ) -> list[GraphEvidence]:
        if top_k < 1:
            return []
        if not self._has_relations(document_id):
            return []
        evidence: list[GraphEvidence] = []
        seen = set()
        for term in self.candidate_terms(question):
            rows = self.client.run_query(
                '''
                MATCH (source:Entity)-[relation:RELATE_TO]->(target:Entity)
                WHERE (
                    source.normalizedName = $term OR source.normalizedName CONTAINS $term
                    OR toLower(source.name) CONTAINS $term
                    OR target.normalizedName = $term OR target.normalizedName CONTAINS $term
                    OR toLower(target.name) CONTAINS $term
                )
                AND ($document_id IS NULL OR relation.documentId = $document_id)
                RETURN source.name AS source_entity,
                       relation.relationType AS relation_type,
                       target.name AS target_entity,
                       relation.description AS description,
                       relation.fileName AS file_name,
                       relation.pageNumber AS page_number,
                       relation.chunkIndex AS chunk_index,
                       relation.chunkId AS chunk_id,
                       relation.confidence AS confidence
                LIMIT $top_k
                ''',
                {'term': term, 'document_id': document_id, 'top_k': top_k - len(evidence)},
            )
            for row in rows:
                key = (
                    row.get('source_entity'),
                    row.get('target_entity'),
                    row.get('chunk_id'),
                    row.get('description'),
                )
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(GraphEvidence.model_validate(row))
                if len(evidence) >= top_k:
                    return evidence
        return evidence

    def _has_relations(self, document_id: str | None) -> bool:
        rows = self.client.run_query(
            '''
            MATCH (source:Entity)-[relation]->(target:Entity)
            WHERE type(relation) = 'RELATE_TO'
              AND ($document_id IS NULL OR relation[$document_property] = $document_id)
            RETURN count(relation) AS total
            LIMIT 1
            ''',
            {'document_id': document_id, 'document_property': 'documentId'},
        )
        return bool(rows and int(rows[0].get('total', 0)) > 0)

    def candidate_terms(self, question: str) -> list[str]:
        normalized = normalize_entity_name(question)
        words = re.findall(r'[\wÀ-ỹ]+', normalized, flags=re.UNICODE)
        useful = [word for word in words if len(word) > 1 and word not in self.STOP_WORDS]
        terms = []
        for size in (3, 2, 1):
            for start in range(0, len(useful) - size + 1):
                term = ' '.join(useful[start:start + size])
                if term not in terms:
                    terms.append(term)
        return terms
