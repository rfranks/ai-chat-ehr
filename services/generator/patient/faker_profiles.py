"""Utilities for generating deterministic synthetic patient profiles with Faker.

This module exposes helpers that seed the Faker instance from a CLI ``--seed``
flag and produce both structured patient demographics and metadata used for
prompt construction. It purposefully avoids depending on FastAPI components so
that it can be executed as a standalone script when preparing fixtures for
manual experimentation.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - exercise fallback when Faker is unavailable
    from faker import Faker as _ExternalFaker
except ImportError:  # pragma: no cover - CI environments without network access
    _ExternalFaker = None

from services.generator.models.patient import Gender, PatientStatus

# Default metadata candidates that feed the synthetic profile generation.
SYMPTOM_CATALOG: Tuple[str, ...] = (
    "fatigue",
    "shortness of breath",
    "chest pain",
    "headache",
    "nausea",
    "dizziness",
    "cough",
    "fever",
    "rash",
    "joint pain",
    "abdominal pain",
)

ETHNICITY_CHOICES: Tuple[str, ...] = (
    "Hispanic or Latino",
    "Not Hispanic or Latino",
    "Asian",
    "Black or African American",
    "White",
    "American Indian or Alaska Native",
    "Native Hawaiian or Other Pacific Islander",
)

FALLBACK_MALE_NAMES: Tuple[str, ...] = (
    "James",
    "Liam",
    "Noah",
    "William",
    "Benjamin",
)

FALLBACK_FEMALE_NAMES: Tuple[str, ...] = (
    "Emma",
    "Olivia",
    "Sophia",
    "Ava",
    "Charlotte",
)

FALLBACK_NONBINARY_NAMES: Tuple[str, ...] = (
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
)

FALLBACK_LAST_NAMES: Tuple[str, ...] = (
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
)

FALLBACK_STREET_NAMES: Tuple[str, ...] = (
    "Maple",
    "Oak",
    "Pine",
    "Cedar",
    "Elm",
)

FALLBACK_STREET_SUFFIXES: Tuple[str, ...] = (
    "St",
    "Ave",
    "Blvd",
    "Ln",
    "Dr",
)

FALLBACK_CITIES: Tuple[str, ...] = (
    "Springfield",
    "Riverton",
    "Franklin",
    "Fairview",
    "Georgetown",
)

FALLBACK_STATE_ABBRS: Tuple[str, ...] = (
    "CA",
    "NY",
    "TX",
    "FL",
    "IL",
    "PA",
    "OH",
    "GA",
    "NC",
    "MI",
)


class _FallbackFaker:
    """Minimal Faker replacement used when the real dependency is unavailable."""

    def __init__(self, locale: str = "en_US") -> None:  # noqa: ARG002 - locale reserved
        self._rng = random.Random()

    def seed_instance(self, seed: Optional[int]) -> None:
        if seed is not None:
            self._rng.seed(seed)

    def first_name_male(self) -> str:
        return self._rng.choice(FALLBACK_MALE_NAMES)

    def first_name_female(self) -> str:
        return self._rng.choice(FALLBACK_FEMALE_NAMES)

    def first_name_nonbinary(self) -> str:
        return self._rng.choice(FALLBACK_NONBINARY_NAMES)

    def first_name(self) -> str:
        combined = FALLBACK_MALE_NAMES + FALLBACK_FEMALE_NAMES + FALLBACK_NONBINARY_NAMES
        return self._rng.choice(combined)

    def last_name(self) -> str:
        return self._rng.choice(FALLBACK_LAST_NAMES)

    def street_address(self) -> str:
        number = self._rng.randint(100, 9999)
        name = self._rng.choice(FALLBACK_STREET_NAMES)
        suffix = self._rng.choice(FALLBACK_STREET_SUFFIXES)
        return f"{number} {name} {suffix}"

    def city(self) -> str:
        return self._rng.choice(FALLBACK_CITIES)

    def state_abbr(self) -> str:
        return self._rng.choice(FALLBACK_STATE_ABBRS)

    def postcode(self) -> str:
        return f"{self._rng.randint(10000, 99999)}"

    def date_of_birth(self, *, minimum_age: int = 0, maximum_age: int = 90) -> date:
        today = date.today()
        min_year = today.year - maximum_age
        max_year = today.year - minimum_age
        start_ordinal = date(min_year, 1, 1).toordinal()
        end_ordinal = min(date(max_year, 12, 31).toordinal(), today.toordinal())
        return date.fromordinal(self._rng.randint(start_ordinal, end_ordinal))


def _create_faker(locale: str = "en_US") -> Any:
    """Return a Faker instance, using a fallback when the package is missing."""

    if _ExternalFaker is not None:
        return _ExternalFaker(locale)
    return _FallbackFaker(locale)


@dataclass(frozen=True)
class PatientAddress:
    """Structured representation of a mailing address."""

    street: str
    city: str
    state: str
    postal_code: str
    country: str


@dataclass(frozen=True)
class PatientStructuredData:
    """Structured patient demographic data returned to downstream services."""

    name_first: str
    name_last: str
    gender: str
    status: str
    dob: str
    ethnicity_description: Optional[str]
    legal_mailing_address: PatientAddress


@dataclass(frozen=True)
class PatientPromptMetadata:
    """Metadata supplied alongside the patient record for LLM prompts."""

    age: int
    age_range: str
    symptom_seeds: List[str]
    seed: Optional[int]


@dataclass(frozen=True)
class PatientProfile:
    """Combined payload with structured data and prompt metadata."""

    patient: PatientStructuredData
    metadata: PatientPromptMetadata


def _configure_rng(seed: Optional[int], rng: Optional[random.Random] = None) -> random.Random:
    """Return an RNG that is optionally seeded for deterministic behaviour."""

    if rng is None:
        return random.Random(seed)
    if seed is not None:
        rng.seed(seed)
    return rng


def _calculate_age(dob: date, *, today: Optional[date] = None) -> int:
    """Return the age in full years for the provided date of birth."""

    today = today or date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)


def _age_range_label(age: int) -> str:
    """Return a coarse age bucket label suitable for prompts."""

    if age < 0:
        raise ValueError("Age cannot be negative")
    if age >= 90:
        return "90+"
    lower = (age // 10) * 10
    upper = lower + 9
    return f"{lower}-{upper}"


def _select_first_name(faker: Any, gender: Gender) -> str:
    """Return a first name aligned with the selected gender when possible."""

    if gender is Gender.MALE:
        return faker.first_name_male()
    if gender is Gender.FEMALE:
        return faker.first_name_female()
    # ``first_name_nonbinary`` is not available in all Faker versions, fall back.
    if hasattr(faker, "first_name_nonbinary"):
        return faker.first_name_nonbinary()  # type: ignore[attr-defined]
    return faker.first_name()


def _generate_address(faker: Any) -> PatientAddress:
    """Return a deterministic mailing address."""

    return PatientAddress(
        street=faker.street_address(),
        city=faker.city(),
        state=faker.state_abbr(),
        postal_code=faker.postcode(),
        country="US",
    )


def generate_patient_profile(
    *,
    seed: Optional[int] = None,
    faker: Optional[Any] = None,
    rng: Optional[random.Random] = None,
) -> PatientProfile:
    """Generate a synthetic patient profile and associated prompt metadata."""

    faker_instance = faker or _create_faker("en_US")
    if seed is not None:
        faker_instance.seed_instance(seed)
    rng_instance = _configure_rng(seed, rng)

    gender = rng_instance.choice(list(Gender))
    status = rng_instance.choice(list(PatientStatus))

    dob = faker_instance.date_of_birth(minimum_age=0, maximum_age=90)
    address = _generate_address(faker_instance)

    ethnicity = rng_instance.choice(ETHNICITY_CHOICES)

    age_years = _calculate_age(dob)
    age_range = _age_range_label(age_years)

    symptom_count = rng_instance.randint(2, 4)
    symptom_seeds = rng_instance.sample(SYMPTOM_CATALOG, symptom_count)

    patient_data = PatientStructuredData(
        name_first=_select_first_name(faker_instance, gender),
        name_last=faker_instance.last_name(),
        gender=gender.value,
        status=status.value,
        dob=dob.isoformat(),
        ethnicity_description=ethnicity,
        legal_mailing_address=address,
    )

    metadata = PatientPromptMetadata(
        age=age_years,
        age_range=age_range,
        symptom_seeds=symptom_seeds,
        seed=seed,
    )

    return PatientProfile(patient=patient_data, metadata=metadata)


def _profile_to_dict(profile: PatientProfile) -> Dict[str, Any]:
    """Convert the dataclass payload to a JSON-serialisable mapping."""

    return {
        "patient": {
            "name_first": profile.patient.name_first,
            "name_last": profile.patient.name_last,
            "gender": profile.patient.gender,
            "status": profile.patient.status,
            "dob": profile.patient.dob,
            "ethnicity_description": profile.patient.ethnicity_description,
            "legal_mailing_address": {
                "street": profile.patient.legal_mailing_address.street,
                "city": profile.patient.legal_mailing_address.city,
                "state": profile.patient.legal_mailing_address.state,
                "postal_code": profile.patient.legal_mailing_address.postal_code,
                "country": profile.patient.legal_mailing_address.country,
            },
        },
        "metadata": {
            "age": profile.metadata.age,
            "age_range": profile.metadata.age_range,
            "symptom_seeds": profile.metadata.symptom_seeds,
            "seed": profile.metadata.seed,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    """Return a CLI argument parser for the Faker profile generator."""

    parser = argparse.ArgumentParser(
        description="Generate deterministic patient profiles for prompt testing.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed that makes Faker output deterministic.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the Faker profile generator CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    profile = generate_patient_profile(seed=args.seed)
    print(json.dumps(_profile_to_dict(profile), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    raise SystemExit(main())
