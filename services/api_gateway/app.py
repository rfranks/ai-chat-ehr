"""API Gateway FastAPI application proxying requests to downstream services."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, Sequence, cast

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.background import BackgroundTask

from shared.http.errors import register_exception_handlers
from shared.observability.logger import configure_logging, get_logger
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

SERVICE_NAME = "api_gateway"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="AI Chat EHR API Gateway")
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)

logger = get_logger(__name__)

PROXY_METHODS = [
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "TRACE",
]

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
_REQUEST_HEADER_EXCLUDE = _HOP_BY_HOP_HEADERS | {"host", "content-length"}
_RESPONSE_HEADER_EXCLUDE = _HOP_BY_HOP_HEADERS | {"content-length"}


class APIGatewaySettings(BaseSettings):
    """Configuration for proxying requests to downstream services."""

    prompt_catalog_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8001"),
        description="Base URL for the prompt catalog service",
    )
    patient_context_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8002"),
        description="Base URL for the patient context service",
    )
    chain_executor_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8003"),
        description="Base URL for the chain executor service",
    )
    http_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="Timeout in seconds for proxied HTTP requests",
    )
    health_timeout: float = Field(
        default=5.0,
        ge=1.0,
        description="Timeout in seconds for health check requests",
    )

    model_config = SettingsConfigDict(
        env_prefix="API_GATEWAY_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> APIGatewaySettings:
    """Return cached API gateway settings."""

    return APIGatewaySettings()


_prompt_client: httpx.AsyncClient | None = None
_patient_client: httpx.AsyncClient | None = None
_chain_client: httpx.AsyncClient | None = None


def _strip_trailing_slash(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def _create_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_strip_trailing_slash(base_url),
        timeout=timeout,
        follow_redirects=True,
    )


async def get_prompt_service_client(
    settings: APIGatewaySettings = Depends(get_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the prompt catalog service."""

    global _prompt_client
    if _prompt_client is None:
        _prompt_client = _create_http_client(
            str(settings.prompt_catalog_url), settings.http_timeout
        )
    return _prompt_client


async def get_patient_service_client(
    settings: APIGatewaySettings = Depends(get_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the patient context service."""

    global _patient_client
    if _patient_client is None:
        _patient_client = _create_http_client(
            str(settings.patient_context_url), settings.http_timeout
        )
    return _patient_client


async def get_chain_service_client(
    settings: APIGatewaySettings = Depends(get_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the chain executor service."""

    global _chain_client
    if _chain_client is None:
        _chain_client = _create_http_client(
            str(settings.chain_executor_url), settings.http_timeout
        )
    return _chain_client


@app.on_event("shutdown")
async def shutdown_http_clients() -> None:
    """Close outbound HTTP clients when the application terminates."""

    global _prompt_client, _patient_client, _chain_client
    clients = [
        ("prompt_catalog", _prompt_client),
        ("patient_context", _patient_client),
        ("chain_executor", _chain_client),
    ]
    for name, client in clients:
        if client is not None:
            try:
                await client.aclose()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                logger.warning(
                    "gateway_client_shutdown_failed",
                    dependency=name,
                    error=str(exc),
                )
    _prompt_client = None
    _patient_client = None
    _chain_client = None


def _filter_request_headers(
    raw_headers: Sequence[tuple[bytes, bytes]],
) -> list[tuple[str, str]]:
    """Return headers suitable for forwarding to an upstream service."""

    forwarded: list[tuple[str, str]] = []
    for key_bytes, value_bytes in raw_headers:
        key = key_bytes.decode("latin-1")
        value = value_bytes.decode("latin-1")
        if key.lower() in _REQUEST_HEADER_EXCLUDE:
            continue
        forwarded.append((key, value))
    return forwarded


def _filter_response_headers(
    headers: Sequence[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Remove hop-by-hop headers from the upstream response."""

    return [
        (key, value)
        for key, value in headers
        if key.lower() not in _RESPONSE_HEADER_EXCLUDE
    ]


async def _proxy_request(
    request: Request,
    client: httpx.AsyncClient,
    service_label: str,
) -> StreamingResponse:
    """Proxy ``request`` to ``client`` and stream back the upstream response."""

    body = await request.body()
    headers = _filter_request_headers(request.headers.raw)
    query_params: list[tuple[str, str | int | float | bool | None]] = [
        (key, value) for key, value in request.query_params.multi_items()
    ]
    proxied_request = client.build_request(
        request.method,
        request.url.path,
        params=query_params,
        headers=headers,
        content=body if body else None,
    )

    try:
        upstream_response = await client.send(proxied_request, stream=True)
    except httpx.TimeoutException as exc:
        logger.warning(
            "gateway_request_timeout",
            service=service_label,
            method=request.method,
            path=request.url.path,
            error=str(exc),
        )
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"{service_label} request timed out",
        ) from exc
    except httpx.RequestError as exc:
        logger.exception(
            "gateway_request_error",
            service=service_label,
            method=request.method,
            path=request.url.path,
            error=str(exc),
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"{service_label} request failed",
        ) from exc

    response_header_pairs = _filter_response_headers(
        list(upstream_response.headers.items())
    )
    response_headers = {key: value for key, value in response_header_pairs}
    background = BackgroundTask(upstream_response.aclose)

    return StreamingResponse(
        upstream_response.aiter_bytes(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        background=background,
    )


async def _check_dependency_health(
    name: str,
    client: httpx.AsyncClient,
    timeout: float,
) -> dict[str, Any]:
    """Return the health status for a downstream dependency."""

    try:
        response = await client.get("/health", timeout=timeout)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning(
            "gateway_health_timeout",
            dependency=name,
            error=str(exc),
        )
        return {
            "status": "timeout",
            "detail": {"message": "Health check request timed out"},
        }
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "gateway_health_status_error",
            dependency=name,
            status_code=exc.response.status_code,
        )
        detail: dict[str, Any] = {"status_code": exc.response.status_code}
        try:
            detail["body"] = exc.response.json()
        except ValueError:
            detail["body"] = exc.response.text
        return {"status": "error", "detail": detail}
    except httpx.RequestError as exc:
        logger.warning(
            "gateway_health_request_error",
            dependency=name,
            error=str(exc),
        )
        return {"status": "unavailable", "detail": {"message": str(exc)}}
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.exception(
            "gateway_health_unexpected_error",
            dependency=name,
            error=str(exc),
        )
        return {"status": "error", "detail": {"message": str(exc)}}

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    reported_status = "unknown"
    if isinstance(payload, dict):
        status_value = payload.get("status")
        if isinstance(status_value, str) and status_value:
            reported_status = status_value

    return {"status": reported_status, "detail": payload}


def _aggregate_health_status(dependencies: dict[str, dict[str, Any]]) -> str:
    """Return the overall health classification based on dependency status."""

    overall = "ok"
    for payload in dependencies.values():
        status_value = str(payload.get("status", "")).lower()
        if status_value in {"unavailable", "timeout", "error"}:
            return "unavailable"
        if status_value not in {"ok", "healthy"}:
            overall = "degraded"
    return overall


@app.get("/health", tags=["health"])
async def health(  # noqa: D417 - FastAPI dependency injection
    settings: APIGatewaySettings = Depends(get_settings),
    prompt_client: httpx.AsyncClient = Depends(get_prompt_service_client),
    patient_client: httpx.AsyncClient = Depends(get_patient_service_client),
    chain_client: httpx.AsyncClient = Depends(get_chain_service_client),
) -> dict[str, Any]:
    """Return API gateway health information including dependency status."""

    dependency_clients = {
        "prompt_catalog": prompt_client,
        "patient_context": patient_client,
        "chain_executor": chain_client,
    }

    checks = await asyncio.gather(
        *(
            _check_dependency_health(name, client, settings.health_timeout)
            for name, client in dependency_clients.items()
        )
    )
    dependency_status = dict(zip(dependency_clients.keys(), checks, strict=True))
    overall_status = _aggregate_health_status(dependency_status)

    return {
        "status": overall_status,
        "service": SERVICE_NAME,
        "dependencies": dependency_status,
    }


prompts_router = APIRouter(prefix="/prompts")
patients_router = APIRouter(prefix="/patients")
chains_router = APIRouter(prefix="/chains")


@prompts_router.api_route("", methods=PROXY_METHODS, include_in_schema=False)
async def proxy_prompts_root(
    request: Request,
    client: httpx.AsyncClient = Depends(get_prompt_service_client),
) -> StreamingResponse:
    """Proxy ``/prompts`` requests to the prompt catalog service."""

    return await _proxy_request(request, client, "prompt_catalog")


@prompts_router.api_route(
    "/{path:path}", methods=PROXY_METHODS, include_in_schema=False
)
async def proxy_prompts(
    path: str,  # noqa: ARG001 - required for routing
    request: Request,
    client: httpx.AsyncClient = Depends(get_prompt_service_client),
) -> StreamingResponse:
    """Proxy nested ``/prompts`` requests to the prompt catalog service."""

    return await _proxy_request(request, client, "prompt_catalog")


@patients_router.api_route("", methods=PROXY_METHODS, include_in_schema=False)
async def proxy_patients_root(
    request: Request,
    client: httpx.AsyncClient = Depends(get_patient_service_client),
) -> StreamingResponse:
    """Proxy ``/patients`` requests to the patient context service."""

    return await _proxy_request(request, client, "patient_context")


@patients_router.api_route(
    "/{path:path}", methods=PROXY_METHODS, include_in_schema=False
)
async def proxy_patients(
    path: str,  # noqa: ARG001 - required for routing
    request: Request,
    client: httpx.AsyncClient = Depends(get_patient_service_client),
) -> StreamingResponse:
    """Proxy nested ``/patients`` requests to the patient context service."""

    return await _proxy_request(request, client, "patient_context")


@chains_router.api_route("", methods=PROXY_METHODS, include_in_schema=False)
async def proxy_chains_root(
    request: Request,
    client: httpx.AsyncClient = Depends(get_chain_service_client),
) -> StreamingResponse:
    """Proxy ``/chains`` requests to the chain executor service."""

    return await _proxy_request(request, client, "chain_executor")


@chains_router.api_route("/{path:path}", methods=PROXY_METHODS, include_in_schema=False)
async def proxy_chains(
    path: str,  # noqa: ARG001 - required for routing
    request: Request,
    client: httpx.AsyncClient = Depends(get_chain_service_client),
) -> StreamingResponse:
    """Proxy nested ``/chains`` requests to the chain executor service."""

    return await _proxy_request(request, client, "chain_executor")


app.include_router(prompts_router)
app.include_router(patients_router)
app.include_router(chains_router)


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return app


__all__ = ["app", "get_app", "health"]
