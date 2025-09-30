"""Replacement strategies for Protected Health Information (PHI).

The anonymizer service uses Microsoft Presidio to detect PHI entities.  Once an
entity is detected we need to replace the sensitive value with either a
deterministic mask or a synthetic alternative.  This module implements a small
policy engine that maps Presidio entity types to replacement callables.

The guiding principles are:

* Repeatable replacements – the same input within a request should yield the
  same anonymised value.  This is handled by :class:`ReplacementContext`, which
  maintains a cache keyed by entity type and source text.
* Deterministic masking – identifiers such as medical record numbers or phone
  numbers are replaced with hashed tokens that preserve format where possible.
* Synthetic generation – human readable fields like names and facility names
  benefit from realistic synthetic replacements.  We support plugging in an
  OpenAI compatible text generator for these cases while still falling back to
  deterministic masking when a generator is not configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import ipaddress
import re
from typing import Callable, Dict, Iterable, Mapping, MutableMapping, Protocol

__all__ = [
    "ReplacementContext",
    "ReplacementStrategy",
    "apply_replacement",
    "register_rule",
]


class TextGenerator(Protocol):
    """Protocol describing the minimum interface for text generation."""

    def generate(self, prompt: str) -> str:  # pragma: no cover - structural typing
        """Return a text completion for ``prompt``."""


ReplacementStrategy = Callable[[str, "ReplacementContext"], str]


@dataclass(slots=True)
class ReplacementContext:
    """State container shared between replacement calls.

    Parameters
    ----------
    generator:
        Optional text generator used for synthetic replacements.  It should
        implement :class:`TextGenerator` – in production this may wrap an
        OpenAI chat completion client while tests can provide lightweight
        fakes.
    salt:
        Arbitrary salt used when hashing values for deterministic masking.
    cache:
        Mapping of (entity type, original text) to the anonymised value.  This
        ensures replacements are repeatable across the same request.
    """

    generator: TextGenerator | None = None
    salt: str = "anonymizer"
    cache: MutableMapping[tuple[str, str], str] = field(default_factory=dict)

    def get_cached(self, entity_type: str, text: str) -> str | None:
        """Return the cached replacement if it exists."""

        return self.cache.get((entity_type.upper(), text))

    def set_cached(self, entity_type: str, text: str, replacement: str) -> None:
        """Cache the replacement for repeatability."""

        self.cache[(entity_type.upper(), text)] = replacement


def _hash_value(value: str, salt: str) -> str:
    """Return a hex digest used for deterministic masking."""

    digest = sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()
    return digest


def _mask_with_prefix(value: str, prefix: str, context: ReplacementContext, length: int = 8) -> str:
    """Return a deterministic token with a readable prefix."""

    digest = _hash_value(value, context.salt)
    return f"{prefix}_{digest[:length]}"


def _hex_to_digits(hex_value: str, length: int) -> str:
    """Convert hex digest to a digit-only string of ``length`` characters."""

    digits = [(int(char, 16) % 10) for char in hex_value]
    converted = "".join(str(d) for d in digits)
    if len(converted) >= length:
        return converted[:length]
    # Pad deterministically if we somehow need more digits
    needed = length - len(converted)
    return (converted + converted[:needed])[:length]


def _mask_phone(value: str, context: ReplacementContext) -> str:
    """Mask a phone number while preserving formatting characters."""

    digits = re.findall(r"\d", value)
    if not digits:
        return _mask_with_prefix(value, "PHONE", context)

    hashed_digits = _hex_to_digits(_hash_value(value, context.salt), len(digits))
    digit_iter = iter(hashed_digits)
    masked_chars = []
    for char in value:
        if char.isdigit():
            masked_chars.append(next(digit_iter))
        else:
            masked_chars.append(char)

    return "".join(masked_chars)


def _mask_email(value: str, context: ReplacementContext) -> str:
    """Mask an email address while keeping the domain recognizable."""

    local_part, sep, domain = value.partition("@")
    if not sep:
        return _mask_with_prefix(value, "EMAIL", context)

    masked_local = _mask_with_prefix(local_part, "user", context, length=12).lower()
    masked_domain = _mask_with_prefix(domain, "domain", context, length=8).lower()
    return f"{masked_local}@{masked_domain}.example"


def _mask_date(value: str, context: ReplacementContext) -> str:
    """Return a pseudonymised date token."""

    digest = _hash_value(value, context.salt)
    offset = int(digest[:4], 16) % 365
    year = 2000 + (int(digest[4:8], 16) % 30)
    return f"{year:04d}-DAY-{offset:03d}"


def _mask_ip(value: str, context: ReplacementContext) -> str:
    """Return a deterministic IPv4 address."""

    digest = _hash_value(value, context.salt)
    octets = [int(digest[i : i + 2], 16) for i in range(0, 8, 2)]
    safe_octets = [(octet % 254) + 1 for octet in octets]
    ip = ".".join(str(octet) for octet in safe_octets)
    try:
        ipaddress.IPv4Address(ip)
    except ipaddress.AddressValueError:  # pragma: no cover - defensive
        return _mask_with_prefix(value, "IP", context)
    return ip


def _generate_synthetic(value: str, context: ReplacementContext, *, prompt: str, prefix: str) -> str:
    """Generate a synthetic replacement using the configured generator."""

    if not context.generator:
        return _mask_with_prefix(value, prefix, context)

    completion = context.generator.generate(prompt.format(original=value)).strip()
    return completion or _mask_with_prefix(value, prefix, context)


def _synthetic_person(value: str, context: ReplacementContext) -> str:
    prompt = (
        "Generate a realistic but fictional full name that is different from the"
        " original: {original}. Return only the name."
    )
    return _generate_synthetic(value, context, prompt=prompt, prefix="PERSON")


def _synthetic_facility(value: str, context: ReplacementContext) -> str:
    prompt = (
        "Create a fictional healthcare facility name distinct from: {original}."
        " Return just the facility name."
    )
    return _generate_synthetic(value, context, prompt=prompt, prefix="FACILITY")


def _synthetic_location(value: str, context: ReplacementContext) -> str:
    prompt = (
        "Provide a fictional city and state combination different from"
        " {original}. Return only the location."
    )
    return _generate_synthetic(value, context, prompt=prompt, prefix="LOCATION")


def _mask_numeric(value: str, context: ReplacementContext, prefix: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return _mask_with_prefix(value, prefix, context)
    masked_digits = _hex_to_digits(_hash_value(value, context.salt), len(digits))
    return f"{prefix}-{masked_digits}"


DEFAULT_RULES: Dict[str, ReplacementStrategy] = {
    "PERSON": _synthetic_person,
    "FACILITY_NAME": _synthetic_facility,
    "MEMBER_ID": lambda value, ctx: _mask_with_prefix(value, "MEMBER", ctx, length=10),
    "MEDICAL_RECORD_NUMBER": lambda value, ctx: _mask_with_prefix(value, "MRN", ctx, length=10),
    "ACCOUNT_NUMBER": lambda value, ctx: _mask_numeric(value, ctx, "ACCT"),
    "PHONE_NUMBER": _mask_phone,
    "EMAIL_ADDRESS": _mask_email,
    "DATE_TIME": _mask_date,
    "LOCATION": _synthetic_location,
    "CITY": _synthetic_location,
    "STATE_OR_PROVINCE": lambda value, ctx: _mask_with_prefix(value, "STATE", ctx, length=6),
    "ZIP_CODE": lambda value, ctx: _mask_numeric(value, ctx, "ZIP"),
    "STREET_ADDRESS": lambda value, ctx: _mask_with_prefix(value, "ADDR", ctx, length=12),
    "AGE": lambda value, ctx: _mask_with_prefix(value, "AGE", ctx, length=4),
    "IP_ADDRESS": _mask_ip,
    "URL": lambda value, ctx: _mask_with_prefix(value, "URL", ctx, length=12),
    "ORGANIZATION": lambda value, ctx: _generate_synthetic(
        value,
        ctx,
        prompt=(
            "Invent a fictional organisation name distinct from {original}."
            " Return only the organisation name."
        ),
        prefix="ORG",
    ),
}


_rules: Dict[str, ReplacementStrategy] = dict(DEFAULT_RULES)


def register_rule(entity_types: Iterable[str], strategy: ReplacementStrategy) -> None:
    """Register or override replacement strategies for ``entity_types``."""

    for entity in entity_types:
        _rules[entity.upper()] = strategy


def apply_replacement(entity_type: str, text: str, context: ReplacementContext | None = None) -> str:
    """Return the anonymised replacement for ``text``.

    The function first checks the context cache to ensure the replacement is
    stable within the same request.  It then resolves the strategy for the
    entity type and applies it.  When no strategy is registered we fall back to
    a deterministic token.
    """

    if context is None:
        context = ReplacementContext()

    cached = context.get_cached(entity_type, text)
    if cached is not None:
        return cached

    strategy = _rules.get(entity_type.upper())
    if strategy is None:
        replacement = _mask_with_prefix(text, entity_type.upper(), context)
    else:
        replacement = strategy(text, context)

    context.set_cached(entity_type, text, replacement)
    return replacement


def get_registered_rules() -> Mapping[str, ReplacementStrategy]:
    """Return a read-only view of the currently registered rules."""

    return dict(_rules)

