from pydantic import BaseModel


class ErrorResponse(BaseModel):
    status: str = 'error'
    message: str
    detail: str | None = None
    error_code: str | None = None
