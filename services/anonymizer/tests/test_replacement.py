import pytest

from services.anonymizer.app.anonymization.replacement import (
    ReplacementContext,
    apply_replacement,
    register_rule,
)


class SequencedGenerator:
    """Simple text generator returning deterministic sequential values."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._responses.pop(0)


def test_person_replacement_uses_generator_and_caches_result():
    generator = SequencedGenerator(["Jane Doe", "Different Name"])
    context = ReplacementContext(generator=generator)

    first = apply_replacement("PERSON", "John Smith", context)
    second = apply_replacement("PERSON", "John Smith", context)

    assert first == "Jane Doe"
    assert second == "Jane Doe", "Replacement should be cached and reused"
    assert len(generator.prompts) == 1
    assert "John Smith" in generator.prompts[0]


def test_person_replacement_falls_back_to_mask_when_no_generator():
    context = ReplacementContext(generator=None, salt="fallback")
    result = apply_replacement("PERSON", "Ada Lovelace", context)
    assert result.startswith("PERSON_")


@pytest.mark.parametrize(
    "value",
    ["(555) 123-9876", "555-123-9876", "+1 555 123 9876"],
)
def test_phone_number_format_is_preserved(value):
    context = ReplacementContext(salt="phone")
    masked = apply_replacement("PHONE_NUMBER", value, context)
    # Formatting characters should be preserved in-place
    for original_char, masked_char in zip(value, masked):
        if original_char.isdigit():
            assert masked_char.isdigit()
        else:
            assert masked_char == original_char
    assert masked != value


def test_email_address_masks_local_and_domain():
    context = ReplacementContext(salt="email")
    masked = apply_replacement("EMAIL_ADDRESS", "alice@example.org", context)
    assert masked.endswith(".example")
    assert masked.startswith("user_")
    assert masked != "alice@example.org"


def test_ip_address_returns_valid_ipv4():
    context = ReplacementContext(salt="ip")
    masked = apply_replacement("IP_ADDRESS", "192.168.0.10", context)
    octets = masked.split(".")
    assert len(octets) == 4
    for part in octets:
        value = int(part)
        assert 0 < value < 255


def test_unknown_entity_uses_default_mask():
    context = ReplacementContext(salt="unknown")
    masked = apply_replacement("UNLISTED", "secret", context)
    assert masked.startswith("UNLISTED_")


def test_custom_rule_registration():
    def custom_strategy(value: str, context: ReplacementContext) -> str:
        return "constant"

    register_rule(["CUSTOM_ENTITY"], custom_strategy)
    context = ReplacementContext()
    assert apply_replacement("CUSTOM_ENTITY", "value", context) == "constant"

