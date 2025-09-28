"""Tests for the model classifier prompt rendering."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[3]))

from shared.llm.chains import model_classifier as classifier_module  # noqa: E402


class _DummyPrompt:
    def __init__(self, template: str) -> None:
        self.template = template

    def format(self, **kwargs: str) -> str:
        rendered = self.template
        for key, value in kwargs.items():
            rendered = rendered.replace(f"{{{key}}}", value)
        return rendered


def test_classifier_prompt_injects_prompt_json() -> None:
    models = classifier_module.DEFAULT_MODEL_CLASSIFIER_MODELS[:1]
    template = classifier_module._CLASSIFIER_TEMPLATE
    template = template.replace(
        "{model_overview}",
        classifier_module._render_model_overview(models),
    )
    template = template.replace(
        "{model_json}", classifier_module._render_model_json(models)
    )
    prompt = _DummyPrompt(template)
    chain = SimpleNamespace(prompt=prompt)

    classifier = classifier_module.ModelClassifier(chain=chain, models=models)

    payload = {"example": "value"}
    rendered = classifier.chain.prompt.format(prompt_json=json.dumps(payload))

    assert "\"example\": \"value\"" in rendered
    assert "{prompt_json}" not in rendered

