"""Problem details and custom exceptions for HTTP responses."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Mapping, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.observability.logger import get_logger

__all__ = [
    "ProblemDetails",
    "ProblemDetailsException",
    "PromptNotFoundError",
    "ProviderUnavailableError",
    "register_exception_handlers",
]

logger = get_logger(__name__)

_PROBLEM_FIELDS = {"type", "title", "status", "detail", "instance"}


class ProblemDetails(BaseModel):
    """Representation of an RFC 7807 problem details payload."""

    type: str = Field(
        default="about:blank", description="URI identifying the error type"
    )
    title: str = Field(
        default="An error occurred", description="Short human-readable summary"
    )
    status: int = Field(default=status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail: str | None = Field(
        default=None, description="Detailed description of the error"
    )
    instance: str | None = Field(
        default=None, description="URI identifying the specific occurrence"
    )
    errors: list[Any] | None = Field(
        default=None, description="Detailed validation errors when applicable"
    )

    model_config = ConfigDict(extra="allow")


class ProblemDetailsException(RuntimeError):
    """Base exception carrying structured problem details metadata."""

    default_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_title = "Service Error"
    default_type = "about:blank"

    def __init__(
        self,
        detail: str | None = None,
        *,
        status_code: int | None = None,
        title: str | None = None,
        type_uri: str | None = None,
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> None:
        message = detail or title or self.default_title
        super().__init__(message)
        self.detail = detail or message
        self.status_code = status_code or self.default_status_code
        self.title = title or self.default_title
        self.problem_type = type_uri or self.default_type
        self.instance = instance
        self.extensions = dict(extensions or {})

    def to_problem_details(self, *, instance: str | None = None) -> ProblemDetails:
        """Return a :class:`ProblemDetails` representation of the exception."""

        payload: dict[str, Any] = dict(self.extensions)
        resolved_instance = instance or self.instance
        return ProblemDetails(
            type=self.problem_type,
            title=self.title,
            status=self.status_code,
            detail=self.detail,
            instance=resolved_instance,
            **payload,
        )


class PromptNotFoundError(ProblemDetailsException):
    """Raised when a requested prompt cannot be located."""

    default_status_code = status.HTTP_404_NOT_FOUND
    default_title = "Prompt Not Found"
    default_type = "https://chatehr.ai/problems/prompt-not-found"

    def __init__(
        self,
        identifier: str,
        *,
        detail: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.identifier = identifier
        message = detail or f"Prompt '{identifier}' was not found."
        super().__init__(
            detail=message,
            status_code=status_code or self.default_status_code,
            title=self.default_title,
            type_uri=self.default_type,
            extensions={"promptId": identifier},
        )


class ProviderUnavailableError(ProblemDetailsException):
    """Raised when an LLM provider cannot be used due to configuration or transient issues."""

    default_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_title = "Provider Unavailable"
    default_type = "https://chatehr.ai/problems/provider-unavailable"

    def __init__(
        self,
        provider: str,
        *,
        detail: str | None = None,
        reason: str | None = None,
        retry_after: float | int | None = None,
        status_code: int | None = None,
    ) -> None:
        self.provider = provider
        self.reason = reason
        extensions: dict[str, Any] = {"provider": provider}
        if reason:
            extensions["reason"] = reason
        if retry_after is not None:
            extensions["retryAfter"] = retry_after
        message = detail or f"The '{provider}' provider is temporarily unavailable."
        super().__init__(
            detail=message,
            status_code=status_code or self.default_status_code,
            title=self.default_title,
            type_uri=self.default_type,
            extensions=extensions,
        )


def _problem_response(problem: ProblemDetails) -> JSONResponse:
    payload = problem.model_dump(mode="json", exclude_none=True)
    status_code = payload.get("status", status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(payload, status_code=status_code)


def _status_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:  # pragma: no cover - defensive branch
        return "HTTP Error"


def _normalize_detail(detail: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(detail, Mapping):
        detail_value = detail.get("detail")
        if detail_value is None:
            detail_value = detail.get("message") or detail.get("error")
        normalized = str(detail_value) if detail_value is not None else None
        extras = {k: v for k, v in detail.items() if k not in _PROBLEM_FIELDS}
        return normalized, extras
    if isinstance(detail, list):
        return None, {"errors": detail}
    if detail is None:
        return None, {}
    return str(detail), {}


def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail, extras = _normalize_detail(exc.detail)
    problem = ProblemDetails(
        type="about:blank",
        title=_status_title(exc.status_code),
        status=exc.status_code,
        detail=detail,
        instance=str(request.url),
        **extras,
    )
    return _problem_response(problem)


def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    problem = ProblemDetails(
        type="https://chatehr.ai/problems/request-validation",
        title="Request Validation Failed",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="One or more request parameters failed validation.",
        instance=str(request.url),
        errors=validation_error.errors(),
    )
    return _problem_response(problem)


def _problem_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    problem_exception = cast(ProblemDetailsException, exc)
    problem = problem_exception.to_problem_details(instance=str(request.url))
    return _problem_response(problem)


def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        error=str(exc),
        path=str(request.url),
    )
    problem = ProblemDetails(
        type="https://chatehr.ai/problems/internal-server-error",
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred while processing the request.",
        instance=str(request.url),
    )
    return _problem_response(problem)


def register_exception_handlers(app: FastAPI) -> None:
    """Register shared exception handlers that emit RFC 7807 problem details."""

    app.add_exception_handler(ProblemDetailsException, _problem_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
