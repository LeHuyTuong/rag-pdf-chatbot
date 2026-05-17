from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import IngestRequest, IngestResponse
from app.pipelines.ingest_pipeline import IngestPipeline

router = APIRouter(prefix='/documents', tags=['documents'])
settings = get_settings()
pipeline = IngestPipeline(settings)


@router.post('/ingest', response_model=IngestResponse)
def ingest(request: IngestRequest):
    return pipeline.ingest(request)


@router.get('/{document_id}/chunks')
def chunks(document_id: str):
    try:
        return pipeline.get_chunks(document_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
