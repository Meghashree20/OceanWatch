from typing import Optional

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorBody