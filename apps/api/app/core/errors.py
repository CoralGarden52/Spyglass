from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, str]] | None = None
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details, request_id=request_id)
    )
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=status,
        headers={**(headers or {}), "X-Request-ID": request_id},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}
        return error_response(
            request,
            exc.status_code,
            codes.get(exc.status_code, "http_error"),
            "请求无法完成",
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo raw inputs: a rejected field can contain a credential or private document.
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "type": error["type"]}
            for error in exc.errors()
        ]
        return error_response(request, 422, "validation_error", "请求参数无效", details)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 500, "internal_error", "服务暂时不可用，请凭请求 ID 排查")
