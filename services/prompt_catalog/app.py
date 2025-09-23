"""Prompt Catalog FastAPI application with stubbed prompt data."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.models.chat import ChatPrompt, ChatPromptKey
from shared.observability.logger import configure_logging
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

from .repositories import PromptRepository, get_prompt_repository

SERVICE_NAME = "prompt_catalog"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="Prompt Catalog Service")
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)


class PromptCollectionResponse(BaseModel):
    """Response payload containing a collection of prompts."""

    prompts: list[ChatPrompt] = Field(default_factory=list)


class PromptResponse(BaseModel):
    """Response payload containing a single prompt."""

    prompt: ChatPrompt


class PromptSearchRequest(BaseModel):
    """Search criteria for locating prompts."""

    query: str | None = Field(
        default=None,
        description="Free-text query to match against prompt metadata and template.",
    )
    key: ChatPromptKey | None = Field(
        default=None, description="Optional canonical prompt key to filter by."
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of prompts to include in the response.",
    )


class PromptSearchResponse(BaseModel):
    """Response payload containing search results."""

    results: list[ChatPrompt] = Field(default_factory=list)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a simple health payload for orchestration checks."""

    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/prompts", response_model=PromptCollectionResponse, tags=["prompts"])
async def list_prompts(
    repository: PromptRepository = Depends(get_prompt_repository),
) -> PromptCollectionResponse:
    """Return all prompts registered in the catalog."""

    prompts = await repository.list_prompts()
    return PromptCollectionResponse(prompts=prompts)


@app.get("/prompts/{prompt_id}", response_model=PromptResponse, tags=["prompts"])
async def get_prompt(
    prompt_id: str,
    repository: PromptRepository = Depends(get_prompt_repository),
) -> PromptResponse:
    """Return a single prompt by ``prompt_id``."""

    prompt = await repository.get_prompt(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")
    return PromptResponse(prompt=prompt)


@app.post("/prompts/search", response_model=PromptSearchResponse, tags=["prompts"])
async def search_prompts(
    payload: PromptSearchRequest,
    repository: PromptRepository = Depends(get_prompt_repository),
) -> PromptSearchResponse:
    """Search prompts using structured criteria."""

    results = await repository.search_prompts(
        query=payload.query,
        key=payload.key,
        limit=payload.limit,
    )
    return PromptSearchResponse(results=results)


def get_app() -> FastAPI:
    """Return the FastAPI app instance."""

    return app


__all__ = ["app", "get_app"]
