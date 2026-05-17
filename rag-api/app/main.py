from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents, rag, debug
from app.api.v1 import chat as v1_chat
from app.api.v1 import debug as v1_debug
from app.api.v1 import documents as v1_documents
from app.api.v1 import health as v1_health
from app.core.config import get_settings
from app.core.constants import SERVICE_NAME
from app.core.exceptions import RagApiException
from app.core.logging import configure_logging, get_logger
from app.infrastructure.mysql.mysql_service import MySqlService

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title='Verifiable PDF RAG API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(debug.router)
app.include_router(v1_health.router)
app.include_router(v1_documents.router)
app.include_router(v1_chat.router)
app.include_router(v1_debug.router)


@app.exception_handler(RagApiException)
async def rag_exception_handler(request: Request, exc: RagApiException):
    return JSONResponse(
        status_code=exc.status_code,
        content={'status': 'error', 'message': exc.message, 'detail': exc.detail, 'error_code': exc.error_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={'status': 'error', 'message': 'Request validation failed', 'detail': str(exc), 'error_code': 'VALIDATION_ERROR'},
    )


@app.get('/')
def root():
    return {'status': 'ok', 'service': SERVICE_NAME, 'docs': '/docs', 'health': '/health'}


@app.on_event('startup')
def startup():
    try:
        MySqlService(get_settings()).init_schema()
    except Exception as error:
        logger.warning('MySQL init warning: %s', error)


@app.get('/health')
def health():
    return {'status': 'ok'}
