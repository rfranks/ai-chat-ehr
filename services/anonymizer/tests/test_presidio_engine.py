import re

import pytest

pytest.importorskip("presidio_analyzer")

from presidio_analyzer import AnalyzerEngine, PatternRecognizer

from services.anonymizer.app.anonymization.presidio_engine import build_analyzer_engine, build_registry


@pytest.fixture()
def registry():
    return build_registry()


def test_registry_includes_predefined_person_recognizer(registry):
    recognizers = registry.get_recognizers(language="en", entities=["PERSON"])
    assert recognizers, "Expected default PERSON recognizer to be available"


def test_facility_name_recognizer_registered(registry):
    recognizers = [
        r
        for r in registry.get_recognizers(language="en")
        if isinstance(r, PatternRecognizer) and "FACILITY_NAME" in r.supported_entities
    ]
    assert recognizers, "Facility name recognizer should be registered"
    facility_recognizer = recognizers[0]
    pattern_regexes = [pattern.regex for pattern in facility_recognizer.patterns]
    assert any("Hospital" in regex for regex in pattern_regexes)
    for regex in pattern_regexes:
        compiled = re.compile(regex)
        assert compiled.search("St. Mary Medical Center")


def test_member_id_recognizer_registered(registry):
    recognizers = [
        r
        for r in registry.get_recognizers(language="en")
        if isinstance(r, PatternRecognizer) and "MEMBER_ID" in r.supported_entities
    ]
    assert recognizers, "Member ID recognizer should be registered"
    member_recognizer = recognizers[0]
    pattern_regexes = [pattern.regex for pattern in member_recognizer.patterns]
    assert any(re.search(regex, "Plan ID: AB12345678") for regex in pattern_regexes)


def test_build_analyzer_engine_uses_registry(registry):
    engine = build_analyzer_engine(nlp_engine=None)
    assert isinstance(engine, AnalyzerEngine)
    # AnalyzerEngine keeps a reference to the registry, so the custom recognizers should be present.
    recognizers = engine.registry.get_recognizers(language="en", entities=["FACILITY_NAME"])
    assert recognizers, "Analyzer engine should expose the custom facility recognizer"
