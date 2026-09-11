from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"


@dataclass(frozen=True, slots=True)
class ProblemException(Exception):
    status: int
    code: str
    title: str
    detail: str


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unavailable")


def _problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": f"urn:seatsafe:problem:{code.replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "correlation_id": _correlation_id(request),
    }
    if extensions:
        content.update(extensions)
    return JSONResponse(status_code=status, content=content, media_type=PROBLEM_MEDIA_TYPE)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def problem_exception_handler(
        request: Request,
        exc: ProblemException,
    ) -> JSONResponse:
        return _problem_response(
            request,
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "location": [str(part) for part in error["loc"]],
                "message": error["msg"],
                "kind": error["type"],
            }
            for error in exc.errors()
        ]
        return _problem_response(
            request,
            status=422,
            code="validation_failed",
            title="Request validation failed",
            detail="One or more request values were invalid.",
            extensions={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            return _problem_response(
                request,
                status=404,
                code="resource_not_found",
                title="Resource not found",
                detail="The requested resource does not exist.",
            )
        return _problem_response(
            request,
            status=exc.status_code,
            code="http_error",
            title="HTTP request failed",
            detail=str(exc.detail),
        )
