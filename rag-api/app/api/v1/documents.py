from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.pipelines.ingest_pipeline import IngestPipeline
from app.schemas.ingest import IngestRequest, IngestResponse

router = APIRouter(prefix='/api/v1/documents', tags=['documents-v1'])
pipeline = IngestPipeline(get_settings())


@router.post('/ingest', response_model=IngestResponse)
def ingest(request: IngestRequest):
    return pipeline.ingest(request)


@router.get('/{document_id}/chunks')
def chunks(document_id: str):
    try:
        return pipeline.get_chunks(document_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
