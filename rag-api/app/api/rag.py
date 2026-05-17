from fastapi import APIRouter
from app.config import get_settings
from app.models.schemas import RagAskRequest, RagAskResponse
from app.pipelines.rag_pipeline import RagPipeline

router = APIRouter(prefix='/rag', tags=['rag'])
settings = get_settings()
pipeline = RagPipeline(settings)


@router.post('/ask', response_model=RagAskResponse)
def ask(request: RagAskRequest):
    return pipeline.ask(request)
