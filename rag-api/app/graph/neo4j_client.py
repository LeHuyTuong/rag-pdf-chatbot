from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from app.config import Settings, get_settings
from app.graph.graph_schema import GraphEntity, GraphRelation


class Neo4jClient:
    def __init__(self, settings: Settings | None = None, driver=None):
        self.settings = settings or get_settings()
        self.database = self.settings.neo4j_database
        self._entity_key_fallback = False
        if driver is not None:
            self.driver = driver
            return
        if not self.settings.neo4j_uri or not self.settings.neo4j_auth:
            raise RuntimeError('Neo4j AuraDB configuration is incomplete')
        self.driver = GraphDatabase.driver(self.settings.neo4j_uri, auth=self.settings.neo4j_auth)

    def __enter__(self) -> 'Neo4jClient':
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()
        self.run_query('RETURN 1 AS connected')

    def close(self) -> None:
        self.driver.close()

    def run_query(self, query: str, params: dict | None = None) -> list[dict]:
        with self.driver.session(database=self.database) as session:
            return [dict(record) for record in session.run(query, params or {})]

    def create_constraints(self) -> dict[str, list[str]]:
        for query in (
            'CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.documentId IS UNIQUE',
            'CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE',
        ):
            self.run_query(query)
        try:
            self.run_query(
                'CREATE CONSTRAINT entity_key_unique IF NOT EXISTS '
                'FOR (e:Entity) REQUIRE (e.normalizedName, e.type) IS UNIQUE'
            )
        except Neo4jError:
            self._entity_key_fallback = True
            self.run_query(
                'CREATE CONSTRAINT entity_key_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entityKey IS UNIQUE'
            )
        entity_constraint = self.run_query(
            "SHOW CONSTRAINTS YIELD name, properties "
            "WHERE name = 'entity_key_unique' RETURN properties"
        )
        if entity_constraint and entity_constraint[0].get('properties') == ['entityKey']:
            self._entity_key_fallback = True
        for query in (
            'CREATE INDEX entity_name_lookup IF NOT EXISTS FOR (e:Entity) ON (e.name)',
            'CREATE INDEX chunk_document_lookup IF NOT EXISTS FOR (c:Chunk) ON (c.documentId)',
        ):
            self.run_query(query)
        return {
            'constraints': [
                row['name']
                for row in self.run_query(
                    "SHOW CONSTRAINTS YIELD name WHERE name IN "
                    "['document_id_unique', 'chunk_id_unique', 'entity_key_unique'] RETURN name ORDER BY name"
                )
            ],
            'indexes': [
                row['name']
                for row in self.run_query(
                    "SHOW INDEXES YIELD name WHERE name IN "
                    "['entity_name_lookup', 'chunk_document_lookup'] RETURN name ORDER BY name"
                )
            ],
        }

    def upsert_document(self, document_id: str, file_name: str, title: str | None = None) -> None:
        self.run_query(
            '''
            MERGE (document:Document {documentId: $document_id})
            ON CREATE SET document.createdAt = datetime()
            SET document.fileName = $file_name,
                document.title = coalesce($title, document.title)
            ''',
            {'document_id': document_id, 'file_name': file_name, 'title': title},
        )

    def upsert_chunk(
        self,
        chunk_id: str,
        document_id: str,
        file_name: str,
        page_number: int | None,
        chunk_index: int | None,
        text: str,
    ) -> None:
        self.upsert_document(document_id, file_name)
        self.run_query(
            '''
            MATCH (document:Document {documentId: $document_id})
            MERGE (chunk:Chunk {chunkId: $chunk_id})
            SET chunk.documentId = $document_id,
                chunk.pageNumber = $page_number,
                chunk.chunkIndex = $chunk_index,
                chunk.textPreview = $text_preview
            MERGE (document)-[:HAS_CHUNK]->(chunk)
            ''',
            {
                'chunk_id': chunk_id,
                'document_id': document_id,
                'page_number': page_number,
                'chunk_index': chunk_index,
                'text_preview': text[:500],
            },
        )

    def upsert_entity(self, entity: GraphEntity, chunk_id: str | None = None) -> None:
        query = (
            'MERGE (entity:Entity {entityKey: $entity_key}) '
            if self._entity_key_fallback
            else 'MERGE (entity:Entity {normalizedName: $normalized_name, type: $type}) '
        )
        query += '''
            SET entity.entityKey = $entity_key,
                entity.name = $name,
                entity.normalizedName = $normalized_name,
                entity.type = $type,
                entity.description = coalesce($description, entity.description)
            WITH entity
            OPTIONAL MATCH (chunk:Chunk {chunkId: $chunk_id})
            FOREACH (_ IN CASE WHEN chunk IS NULL THEN [] ELSE [1] END |
                MERGE (chunk)-[:MENTIONS]->(entity)
            )
        '''
        self.run_query(
            query,
            {
                'entity_key': entity.entity_key,
                'name': entity.name,
                'normalized_name': entity.normalized_name,
                'type': entity.type,
                'description': entity.description,
                'chunk_id': chunk_id,
            },
        )

    def upsert_relation(self, relation: GraphRelation) -> None:
        if not relation.chunk_id or not relation.document_id or not relation.file_name:
            raise ValueError('Cannot create relation without source chunk metadata')
        self.upsert_entity(relation.source_entity, relation.chunk_id)
        self.upsert_entity(relation.target_entity, relation.chunk_id)
        self.run_query(
            '''
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MATCH (source:Entity {entityKey: $source_key})
            MATCH (target:Entity {entityKey: $target_key})
            MERGE (chunk)-[:MENTIONS]->(source)
            MERGE (chunk)-[:MENTIONS]->(target)
            MERGE (source)-[relation:RELATE_TO {
                chunkId: $chunk_id,
                relationType: $relation_type,
                targetEntityKey: $target_key
            }]->(target)
            SET relation.description = $description,
                relation.confidence = $confidence,
                relation.documentId = $document_id,
                relation.fileName = $file_name,
                relation.pageNumber = $page_number,
                relation.chunkIndex = $chunk_index
            ''',
            {
                'source_key': relation.source_entity.entity_key,
                'target_key': relation.target_entity.entity_key,
                'relation_type': relation.relation_type,
                'description': relation.description,
                'confidence': relation.confidence,
                'document_id': relation.document_id,
                'file_name': relation.file_name,
                'page_number': relation.page_number,
                'chunk_index': relation.chunk_index,
                'chunk_id': relation.chunk_id,
            },
        )

    def clear_chunk_evidence(self, chunk_id: str) -> None:
        self.run_query(
            '''
            MATCH ()-[relation:RELATE_TO]->()
            WHERE relation.chunkId = $chunk_id
            DELETE relation
            ''',
            {'chunk_id': chunk_id},
        )
        self.run_query(
            '''
            MATCH (chunk:Chunk {chunkId: $chunk_id})-[mention:MENTIONS]->()
            DELETE mention
            ''',
            {'chunk_id': chunk_id},
        )

    def clear_document(self, document_id: str) -> None:
        self.run_query(
            '''
            MATCH ()-[relation:RELATE_TO]->()
            WHERE relation.documentId = $document_id
            DELETE relation
            ''',
            {'document_id': document_id},
        )
        self.run_query(
            '''
            MATCH (document:Document {documentId: $document_id})
            OPTIONAL MATCH (document)-[:HAS_CHUNK]->(chunk:Chunk)
            DETACH DELETE document, chunk
            ''',
            {'document_id': document_id},
        )
        self.run_query(
            '''
            MATCH (entity:Entity)
            WHERE NOT (entity)<-[:MENTIONS]-(:Chunk)
              AND NOT (entity)-[:RELATE_TO]-(:Entity)
            DELETE entity
            '''
        )

    def counts(self, document_id: str | None = None) -> dict[str, int]:
        params = {'document_id': document_id}
        nodes = self.run_query(
            '''
            OPTIONAL MATCH (document:Document)
            WHERE $document_id IS NULL OR document.documentId = $document_id
            WITH count(DISTINCT document) AS documents
            OPTIONAL MATCH (chunk:Chunk)
            WHERE $document_id IS NULL OR chunk.documentId = $document_id
            WITH documents, count(DISTINCT chunk) AS chunks
            OPTIONAL MATCH (entity:Entity)
            RETURN documents, chunks, count(DISTINCT entity) AS entities
            ''',
            params,
        )[0]
        relation = self.run_query(
            '''
            MATCH ()-[relation]->()
            WHERE type(relation) = 'RELATE_TO'
              AND ($document_id IS NULL OR relation[$document_property] = $document_id)
            RETURN count(relation) AS relations
            ''',
            {**params, 'document_property': 'documentId'},
        )[0]
        return {**nodes, 'relations': relation['relations']}
