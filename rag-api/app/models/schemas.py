from datetime import datetime, timezone
from pydantic import BaseModel, Field


class PageText(BaseModel):
    page_number: int
    text: str
    char_start: int = 0
    char_end: int = 0


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    user_id: str
    chunk_index: int
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    token_count: int
    content: str
    chunk_reason: str
    file_name: str
    qdrant_point_id: str | None = None


class IngestRequest(BaseModel):
    user_id: str
    document_id: str
    file_path: str
    file_name: str


class IngestResponse(BaseModel):
    document_id: str
    status: str
    total_pages: int
    total_chunks: int
    chunk_report_path: str
    extracted_text_length: int = 0
    parser_used: str | None = None
    error_message: str | None = None
    warning: str | None = None
    chunks: list[Chunk] = Field(default_factory=list)


class RagAskRequest(BaseModel):
    user_id: str
    document_id: str
    session_id: str
    message_id: str
    question: str


class Source(BaseModel):
    chunk_id: str
    file_name: str
    page_start: int
    page_end: int
    score: float
    support_level: str
    preview: str | None = None


class RagAskResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[Source]
    related_chunks: list[Source] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    answer_type: str = 'answered'
    warning: str | None = None
    retrieval_report_path: str
    answer_report_path: str


class RetrievedChunk(BaseModel):
    chunk: Chunk
    vector_score: float
    keyword_score: float
    final_score: float
    selected_for_context: bool
    reason: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
