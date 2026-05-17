from fastapi import APIRouter

from app.core.config import get_settings
from app.pipelines.rag_pipeline import RagPipeline
from app.schemas.chat import RagAskRequest, RagAskResponse

router = APIRouter(prefix='/api/v1/chat', tags=['chat-v1'])
pipeline = RagPipeline(get_settings())


@router.post('/ask', response_model=RagAskResponse)
def ask(request: RagAskRequest):
    return pipeline.ask(request)
