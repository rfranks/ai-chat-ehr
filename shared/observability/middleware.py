"""Reusable FastAPI middleware for observability instrumentation."""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .logger import generate_request_id, get_logger, request_context

__all__ = ["CorrelationIdMiddleware", "RequestTimingMiddleware"]


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Populate a request identifier and propagate it through the response."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        header_name: str = "X-Request-ID",
        correlation_header: str = "X-Correlation-ID",
        additional_headers: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.correlation_header = correlation_header or header_name
        candidates = [
            self.header_name,
            self.correlation_header,
            "X-Request-ID",
            "X-Correlation-ID",
        ]
        if additional_headers:
            candidates.extend(additional_headers)
        # Remove duplicates while preserving order.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in candidates:
            normalized = name.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(normalized)
        self._candidate_headers = ordered

    def _resolve_request_id(self, request: Request) -> str:
        for header in self._candidate_headers:
            value = request.headers.get(header)
            if value:
                candidate = value.strip()
                if candidate:
                    return candidate[:128]
        return generate_request_id()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = self._resolve_request_id(request)
        request.state.request_id = request_id
        request.state.correlation_id = request_id
        request.scope["request_id"] = request_id
        request.scope["correlation_id"] = request_id

        with request_context(request_id=request_id):
            response = await call_next(request)

        response.headers.setdefault(self.header_name, request_id)
        response.headers.setdefault(self.correlation_header, request_id)
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Measure request latency and emit structured log entries."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        header_name: str = "X-Response-Time",
    ) -> None:
        super().__init__(app)
        self._header_name = header_name
        self._logger = get_logger("http")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        client = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._logger.bind(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                client=client,
                user_agent=user_agent,
            ).exception("http_request_failed")
            raise

        duration_ms = (time.perf_counter() - start) * 1000.0
        if self._header_name:
            response.headers[self._header_name] = f"{duration_ms / 1000.0:.6f}s"

        self._logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client=client,
            user_agent=user_agent,
        ).info("http_request_completed")

        return response
