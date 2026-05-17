from fastapi import status


class RagApiException(Exception):
    def __init__(self, message: str, *, detail: str | None = None, error_code: str = 'RAG_API_ERROR', status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class IngestPipelineException(RagApiException):
    def __init__(self, message: str, *, detail: str | None = None, error_code: str = 'INGEST_FAILED'):
        super().__init__(message, detail=detail, error_code=error_code, status_code=status.HTTP_400_BAD_REQUEST)


class RetrievalPipelineException(RagApiException):
    def __init__(self, message: str, *, detail: str | None = None, error_code: str = 'RETRIEVAL_FAILED'):
        super().__init__(message, detail=detail, error_code=error_code, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
