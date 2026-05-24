import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


EntityType = Literal['PERSON', 'EVENT', 'ORG', 'PLACE', 'CONCEPT', 'POLICY', 'PERIOD', 'IMPACT', 'ACTION']
RelationType = Literal['RELATE_TO']


def normalize_entity_name(name: str) -> str:
    return re.sub(r'\s+', ' ', (name or '').strip().lower())


class GraphEntity(BaseModel):
    name: str
    normalized_name: str = ''
    type: EntityType
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode='after')
    def set_normalized_name(self) -> 'GraphEntity':
        self.name = re.sub(r'\s+', ' ', self.name.strip())
        self.normalized_name = normalize_entity_name(self.normalized_name or self.name)
        if self.description is not None:
            self.description = re.sub(r'\s+', ' ', self.description.strip()) or None
        return self

    @property
    def entity_key(self) -> str:
        return f'{self.normalized_name}::{self.type}'


class GraphRelation(BaseModel):
    source_entity: GraphEntity
    target_entity: GraphEntity
    relation_type: RelationType = 'RELATE_TO'
    description: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    chunk_id: str
    document_id: str
    file_name: str
    page_number: int | None
    chunk_index: int | None

    @model_validator(mode='after')
    def require_source_metadata(self) -> 'GraphRelation':
        self.description = re.sub(r'\s+', ' ', self.description.strip())
        self.chunk_id = self.chunk_id.strip()
        self.document_id = self.document_id.strip()
        self.file_name = self.file_name.strip()
        if not self.description or not self.chunk_id or not self.document_id or not self.file_name:
            raise ValueError('A relation requires description and source chunk metadata')
        return self


class GraphExtractionResult(BaseModel):
    entities: list[GraphEntity] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)


class GraphEvidence(BaseModel):
    source_entity: str
    relation_type: str
    target_entity: str
    description: str
    file_name: str | None = None
    page_number: int | None = None
    chunk_index: int | None = None
    chunk_id: str | None = None
    confidence: float | None = None


class GraphChunk(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    page_number: int | None = None
    chunk_index: int | None = None
    text: str

    @model_validator(mode='after')
    def ensure_chunk_id(self) -> 'GraphChunk':
        if not self.chunk_id:
            self.chunk_id = f'{self.document_id}_{self.page_number}_{self.chunk_index}'
        return self
