from fastapi import APIRouter
from app.config import get_settings
from app.services.report_service import ReportService

router = APIRouter(prefix='/debug', tags=['debug'])
reports = ReportService(get_settings())


@router.get('/documents/{document_id}/chunk-report')
def chunk_report(document_id: str):
    return reports.read(f'chunk_report_{document_id}.json')


@router.get('/chat/{message_id}/retrieval-report')
def retrieval_report(message_id: str):
    return reports.read(f'retrieval_report_{message_id}.json')


@router.get('/chat/{message_id}/answer-report')
def answer_report(message_id: str):
    return reports.read(f'answer_report_{message_id}.json')
