from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.generator.models.patient import Gender, PatientStatus
from services.generator.patient.faker_profiles import (
    _age_range_label,
    _calculate_age,
    generate_patient_profile,
    main,
)


def test_generate_patient_profile_respects_seed() -> None:
    first = generate_patient_profile(seed=123)
    second = generate_patient_profile(seed=123)

    assert first == second


def test_generate_patient_profile_populates_required_fields() -> None:
    profile = generate_patient_profile(seed=101)

    assert profile.patient.name_first
    assert profile.patient.name_last
    assert profile.patient.gender in {gender.value for gender in Gender}
    assert profile.patient.status in {status.value for status in PatientStatus}
    assert profile.patient.legal_mailing_address.street
    assert profile.patient.legal_mailing_address.city
    assert profile.patient.legal_mailing_address.state
    assert profile.metadata.symptom_seeds
    assert 2 <= len(profile.metadata.symptom_seeds) <= 4
    assert profile.metadata.age_range == _age_range_label(profile.metadata.age)
    assert profile.metadata.seed == 101


def test_age_helpers_return_expected_values() -> None:
    dob = date(2000, 5, 1)
    today = date(2024, 5, 2)
    assert _calculate_age(dob, today=today) == 24
    assert _age_range_label(24) == "20-29"
    assert _age_range_label(90) == "90+"
    with pytest.raises(ValueError):
        _age_range_label(-1)


def test_cli_output_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", "42"]) == 0
    first_output = capsys.readouterr().out

    assert main(["--seed", "42"]) == 0
    second_output = capsys.readouterr().out

    assert first_output == second_output

    payload = json.loads(first_output)
    assert payload["metadata"]["seed"] == 42
    assert payload["patient"]["status"] in {status.value for status in PatientStatus}
