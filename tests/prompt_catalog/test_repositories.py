import pytest

from shared.models.chat import ChatPrompt, ChatPromptKey

from services.prompt_catalog.repositories import (
    PromptRepository,
    _DEFAULT_PROMPTS,
    get_prompt_repository,
)


def _create_repository() -> PromptRepository:
    prompt = ChatPrompt(
        key=ChatPromptKey.PATIENT_CONTEXT,
        title="Example Prompt",
        template="Hello {name}",
        input_variables=["name"],
    )
    return PromptRepository([prompt])


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_search_prompts_negative_limit_returns_empty_list() -> None:
    repository = _create_repository()

    results = await repository.search_prompts(limit=-5)

    assert results == []


@pytest.mark.anyio("asyncio")
async def test_search_prompts_zero_limit_returns_empty_list() -> None:
    repository = _create_repository()

    results = await repository.search_prompts(limit=0)

    assert results == []


@pytest.mark.anyio("asyncio")
async def test_get_prompt_accepts_string_identifier() -> None:
    repository = _create_repository()

    result = await repository.get_prompt("patient_context")

    assert result is not None
    assert result.key is ChatPromptKey.PATIENT_CONTEXT


@pytest.mark.anyio("asyncio")
async def test_get_prompt_accepts_enum_repr() -> None:
    repository = _create_repository()

    result = await repository.get_prompt("ChatPromptKey.PATIENT_CONTEXT")

    assert result is not None
    assert result.key is ChatPromptKey.PATIENT_CONTEXT


@pytest.mark.anyio("asyncio")
async def test_prompt_identifier_skips_blank_metadata_id() -> None:
    prompt = ChatPrompt(
        title="Example Prompt",
        template="Hello",
        metadata={"id": "   "},
    )
    repository = PromptRepository([prompt])

    empty_lookup = await repository.get_prompt("   ")
    title_lookup = await repository.get_prompt("Example Prompt")

    assert empty_lookup is None
    assert title_lookup is prompt


@pytest.mark.anyio("asyncio")
async def test_search_prompts_matches_metadata_values() -> None:
    prompt = ChatPrompt(
        title="Example Prompt",
        template="Hello",
        metadata={"clinical_area": "Cardiology"},
    )
    repository = PromptRepository([prompt])

    results = await repository.search_prompts(query="cardiology")

    assert results == [prompt]


@pytest.mark.anyio("asyncio")
async def test_default_prompt_catalog_contains_expected_prompts() -> None:
    repository = get_prompt_repository()

    prompts = await repository.list_prompts()

    assert len(prompts) == len(_DEFAULT_PROMPTS)

    expected_keys = {
        ChatPromptKey.PATIENT_CONTEXT,
        ChatPromptKey.CLINICAL_PLAN,
        ChatPromptKey.FOLLOW_UP_QUESTIONS,
        ChatPromptKey.PATIENT_SUMMARY,
        ChatPromptKey.DIFFERENTIAL_DIAGNOSIS,
        ChatPromptKey.PATIENT_EDUCATION,
        ChatPromptKey.SAFETY_CHECKS,
        ChatPromptKey.TRIAGE_ASSESSMENT,
    }

    for key in expected_keys:
        prompt = await repository.get_prompt(key)
        assert prompt is not None
        assert prompt.key is key
