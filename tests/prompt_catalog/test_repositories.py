from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.models.chat import ChatPrompt, ChatPromptKey

from services.prompt_catalog.repositories import PromptRepository


def _create_repository() -> PromptRepository:
    prompt = ChatPrompt(
        key=ChatPromptKey.PATIENT_CONTEXT,
        title="Example Prompt",
        template="Hello {name}",
        input_variables=["name"],
    )
    return PromptRepository([prompt])


@pytest.mark.asyncio
async def test_search_prompts_negative_limit_returns_empty_list() -> None:
    repository = _create_repository()

    results = await repository.search_prompts(limit=-5)

    assert results == []


@pytest.mark.asyncio
async def test_search_prompts_zero_limit_returns_empty_list() -> None:
    repository = _create_repository()

    results = await repository.search_prompts(limit=0)

    assert results == []


@pytest.mark.asyncio
async def test_get_prompt_accepts_string_identifier() -> None:
    repository = _create_repository()

    result = await repository.get_prompt("patient_context")

    assert result is not None
    assert result.key is ChatPromptKey.PATIENT_CONTEXT


@pytest.mark.asyncio
async def test_get_prompt_accepts_enum_repr() -> None:
    repository = _create_repository()

    result = await repository.get_prompt("ChatPromptKey.PATIENT_CONTEXT")

    assert result is not None
    assert result.key is ChatPromptKey.PATIENT_CONTEXT
