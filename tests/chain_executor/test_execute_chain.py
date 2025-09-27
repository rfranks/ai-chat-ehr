import importlib
import re
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _stub_logger_module(monkeypatch: pytest.MonkeyPatch):
    """Provide a lightweight stand-in for the shared logger module."""

    module_name = "shared.observability.logger"
    stub = types.ModuleType(module_name)

    class _DummyLogger:
        def bind(
            self, *args: object, **kwargs: object
        ) -> "_DummyLogger":  # pragma: no cover - stub
            return self

        def info(
            self, *args: object, **kwargs: object
        ) -> None:  # pragma: no cover - stub
            return None

        def warning(
            self, *args: object, **kwargs: object
        ) -> None:  # pragma: no cover - stub
            return None

        def exception(
            self, *args: object, **kwargs: object
        ) -> None:  # pragma: no cover - stub
            return None

        def contextualize(
            self, *args: object, **kwargs: object
        ):  # pragma: no cover - stub
            @contextmanager
            def _ctx():
                yield None

            return _ctx()

    def get_logger(name: str | None = None) -> _DummyLogger:  # pragma: no cover - stub
        return _DummyLogger()

    stub.get_logger = get_logger  # type: ignore[attr-defined]
    stub.configure_logging = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    stub.generate_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]
    stub.get_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]

    @contextmanager
    def request_context(*args: object, **kwargs: object):  # pragma: no cover - stub
        yield "test-request-id"

    stub.request_context = request_context  # type: ignore[attr-defined]

    audit_module = types.ModuleType("shared.observability.audit")

    class _AuditRepository:
        async def persist(self, audit: Any) -> None:  # pragma: no cover - stub
            self.last_audit = audit

    class _StdoutAuditRepository(_AuditRepository):
        pass

    class _ChatAudit:
        def __init__(self, event: str, **kwargs: Any) -> None:
            self.event = event
            for key, value in kwargs.items():
                setattr(self, key, value)

        def to_dict(self) -> dict[str, Any]:  # pragma: no cover - stub
            return dict(self.__dict__)

    _DEFAULT_REPOSITORY = _StdoutAuditRepository()

    def get_audit_repository() -> _AuditRepository:  # pragma: no cover - stub
        return _DEFAULT_REPOSITORY

    async def record_chat_audit(
        event: str,
        *,
        repository: _AuditRepository | None = None,
        **kwargs: Any,
    ) -> _ChatAudit:
        repo = repository or get_audit_repository()
        audit = _ChatAudit(event, **kwargs)
        await repo.persist(audit)
        return audit

    audit_module.ChatAudit = _ChatAudit  # type: ignore[attr-defined]
    audit_module.AuditRepository = _AuditRepository  # type: ignore[attr-defined]
    audit_module.StdoutAuditRepository = _StdoutAuditRepository  # type: ignore[attr-defined]
    audit_module.get_audit_repository = get_audit_repository  # type: ignore[attr-defined]
    audit_module.record_chat_audit = record_chat_audit  # type: ignore[attr-defined]
    audit_module.__all__ = [  # pragma: no cover - stub metadata
        "ChatAudit",
        "AuditRepository",
        "StdoutAuditRepository",
        "get_audit_repository",
        "record_chat_audit",
    ]

    monkeypatch.setitem(sys.modules, module_name, stub)
    monkeypatch.setitem(sys.modules, "shared.observability.audit", audit_module)
    try:
        yield
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop("shared.observability.audit", None)


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio-powered tests to the asyncio backend."""

    return "asyncio"


class DummyPromptCatalogClient:
    """Return a canned prompt regardless of the requested key."""

    def __init__(self, prompt: Any) -> None:
        self.prompt = prompt
        self.calls: list[Any] = []

    async def get_prompt(self, identifier: Any) -> Any:
        self.calls.append(identifier)
        return self.prompt


class DummyPatientContextClient:
    """Stub patient context client that should never be invoked."""

    async def get_patient_context(
        self, patient_id: str
    ) -> Any:  # pragma: no cover - defensive
        raise AssertionError("Patient context lookup was not expected during this test")


class DummyLLM:
    """Record invocations and return deterministic responses."""

    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    async def ainvoke(
        self,
        prompt_text: str,
        *,
        output_key: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = {
            "prompt": prompt_text,
            "output_key": output_key,
            "variables": dict(variables),
        }
        self.calls.append(record)
        return {output_key: f"LLM response for: {prompt_text}"}


class DummyLLMChain:
    """Minimal replacement for ``langchain``'s :class:`LLMChain`."""

    def __init__(self, llm: DummyLLM, prompt: Any, output_key: str) -> None:
        self.llm = llm
        self.prompt = prompt
        self.output_key = output_key

    async def ainvoke(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        rendered = self.prompt.format(**variables)
        return await self.llm.ainvoke(
            rendered,
            output_key=self.output_key,
            variables=variables,
        )


class DummyClassifierChain:
    """Capture invocations from the category classifier."""

    output_key = "categories"

    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

    async def ainvoke(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(dict(variables))
        return {self.output_key: '["general_reasoning"]'}


class DummyClassifierInstance:
    """Classifier stub returning a fixed category assignment."""

    def __init__(self) -> None:
        self.chain = DummyClassifierChain()
        self.parse_calls: list[str] = []

    def parse_response(self, text: str) -> list[str]:
        self.parse_calls.append(text)
        return ["general_reasoning"]


@pytest.mark.anyio
async def test_execute_chain_uses_prompt_enum_and_classifies_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain_app = importlib.import_module("services.chain_executor.app")
    chat_models = importlib.import_module("shared.models.chat")
    prompt_builder = importlib.import_module("shared.llm.prompt_builder")
    openai_adapter = importlib.import_module("shared.llm.adapters.openai")

    ChatPrompt = chat_models.ChatPrompt
    ChatPromptKey = chat_models.ChatPromptKey
    PromptTemplateSpec = prompt_builder.PromptTemplateSpec
    MissingPromptTemplateError = prompt_builder.MissingPromptTemplateError

    class DummyPromptTemplate:
        def __init__(self, text: str) -> None:
            self._text = text
            pattern = re.compile(r"{([^{}]+)}")
            # Preserve declaration order while removing duplicates.
            self.input_variables = tuple(dict.fromkeys(pattern.findall(text)))

        def format(self, **variables: Any) -> str:
            if not self.input_variables:
                return self._text
            return self._text.format(**variables)

    def fake_build_prompt_template(prompt: Any) -> PromptTemplateSpec:
        text = (getattr(prompt, "template", "") or "").strip()
        if not text:
            raise MissingPromptTemplateError(
                "Prompt definition is missing template text"
            )
        template = DummyPromptTemplate(text)
        return PromptTemplateSpec(
            template=template, input_variables=template.input_variables
        )

    monkeypatch.setattr(chain_app, "build_prompt_template", fake_build_prompt_template)

    dummy_llm = DummyLLM()
    monkeypatch.setattr(
        openai_adapter, "get_chat_model", lambda *args, **kwargs: dummy_llm
    )
    monkeypatch.setattr(chain_app, "LLMChain", DummyLLMChain)
    monkeypatch.setattr(chain_app, "_CATEGORY_CLASSIFICATION_CACHE", {})

    classifier_instances: list[DummyClassifierInstance] = []
    create_calls: list[Dict[str, Any]] = []

    def fake_classifier_create(
        cls, llm: Any, categories: Any = None
    ) -> DummyClassifierInstance:
        instance = DummyClassifierInstance()
        classifier_instances.append(instance)
        create_calls.append({"llm": llm, "categories": categories})
        return instance

    monkeypatch.setattr(
        chain_app.CategoryClassifier,
        "create",
        classmethod(fake_classifier_create),
    )

    prompt_definition = ChatPrompt(
        key=ChatPromptKey.PATIENT_SUMMARY,
        template="Patient summary: {symptom}",
        input_variables=["symptom"],
        metadata={},
    )
    prompt_client = DummyPromptCatalogClient(prompt_definition)
    patient_client = DummyPatientContextClient()

    app = chain_app.get_app()

    async def _prompt_client_override() -> DummyPromptCatalogClient:
        return prompt_client

    async def _patient_client_override() -> DummyPatientContextClient:
        return patient_client

    app.dependency_overrides[chain_app.get_prompt_catalog_client] = (
        _prompt_client_override
    )
    app.dependency_overrides[chain_app.get_patient_context_client] = (
        _patient_client_override
    )

    payload = {
        "chain": [{"promptEnum": "PATIENT_SUMMARY"}],
        "variables": {"symptom": "persistent cough"},
        "modelProvider": "openai/gpt-3.5-turbo",
    }

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.post("/chains/execute", json=payload)
    finally:
        app.dependency_overrides.pop(chain_app.get_prompt_catalog_client, None)
        app.dependency_overrides.pop(chain_app.get_patient_context_client, None)

    assert response.status_code == 200
    body = response.json()

    expected_prompt = "Patient summary: persistent cough"
    expected_output = f"LLM response for: {expected_prompt}"

    assert body["finalOutputKey"] == "patient_summary"
    assert body["finalOutput"] == expected_output
    assert body["outputs"] == {"patient_summary": expected_output}
    assert body["steps"][0]["prompt"]["template"] == "Patient summary: {symptom}"

    assert prompt_client.calls, "Prompt catalog client was not invoked"
    assert prompt_client.calls[0] == ChatPromptKey.PATIENT_SUMMARY

    assert len(dummy_llm.calls) == 1
    llm_call = dummy_llm.calls[0]
    assert llm_call["prompt"] == expected_prompt
    assert llm_call["output_key"] == "patient_summary"
    assert llm_call["variables"]["symptom"] == "persistent cough"

    assert create_calls, "Category classifier was not instantiated"
    classifier = classifier_instances[0]
    assert classifier.chain.calls, "Classifier chain was not executed"
    assert "prompt_json" in classifier.chain.calls[0]
    assert classifier.parse_calls == ['["general_reasoning"]']

    step_metadata = body["steps"][0]["prompt"].get("metadata", {})
    assert step_metadata.get("categories") == ["general_reasoning"]
