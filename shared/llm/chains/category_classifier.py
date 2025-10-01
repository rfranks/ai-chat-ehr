"""Chains that classify prompts into thematic categories."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

__all__ = [
    "PromptEMRDataCategory",
    "DEFAULT_PROMPT_CATEGORIES",
    "CategoryClassifier",
]


@dataclass(frozen=True)
class PromptEMRDataCategory:
    """Structured metadata for an EMR data category for a Prompt.
    Hints to the classifier about the EMR data required to answer the question.
    """

    slug: str
    name: str
    description: str
    aliases: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the category."""

        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "aliases": list(self.aliases),
        }


DEFAULT_PROMPT_CATEGORIES: tuple[PromptEMRDataCategory, ...] = (
    # — Core demographics —
    PromptEMRDataCategory(
        slug="patientDetail",
        name="Patient Demographics",
        description="""
        Basic patient information such as age, race, ethnicity, sex assigned at birth, gender identity,
        preferred language, social determinants of health, addresses, phone numbers, and emergency contacts.
        Includes date of birth, date of death (if applicable), MRN(s), identifiers, and legal name variants.
        Include first name, last name, and full name as well.
        """,
        aliases=("demographics", "details", "patientInfo", "identity"),
    ),
    # — Labs / tests / vitals / notes (existing, tightened) —
    PromptEMRDataCategory(
        slug="labs",
        name="Lab Results",
        description="""
        Laboratory results only (e.g., blood/urine/other analytes). Includes panel/component structure,
        values, units, reference ranges, abnormal flags, interpretations, collection times, and resulted times.
        Examples: CBC, CMP, lipid panel, HbA1c, thyroid panel, urinalysis, cultures with sensitivities.
        """,
        aliases=("lab", "labResults", "laboratory", "labPanels"),
    ),
    PromptEMRDataCategory(
        slug="testResults",
        name="Test Results",
        description="""
        Diagnostic/procedural result reports outside of core labs: imaging (X-ray, CT, MRI, US),
        echocardiograms, ECGs, pathology reports, and other procedural narratives.
        Include key findings, impressions, measurements, and dates/times.
        """,
        aliases=(
            "test",
            "tests",
            "procedure",
            "procedures",
            "imagingResults",
            "echo",
            "ecg",
            "pathology",
        ),
    ),
    PromptEMRDataCategory(
        slug="vitals",
        name="Vitals",
        description="""
        Vital signs including blood pressure, heart rate, respiratory rate, temperature, SpO₂, pain score,
        height, weight, BMI, and device/context (e.g., cuff size/position) when available, with timestamps.
        """,
        aliases=("vitalSigns", "vital_signs", "observations"),
    ),
    PromptEMRDataCategory(
        slug="notes",
        name="Clinical Notes",
        description="""
        Unstructured notes: H&P, progress notes, consults, discharge summaries, operative notes,
        procedure notes, ED notes, and other documentation. Include author, specialty, note type, and dates.
        """,
        aliases=("documentation", "clinical_notes", "clinicalNotes", "narratives"),
    ),
    # — Medications & medication administrations —
    PromptEMRDataCategory(
        slug="medications",
        name="Medication List",
        description="""
        Active and historical medications (home and inpatient): generic/brand, dose, route, frequency,
        PRN vs scheduled, start/stop dates, indications, last reconciliation, status (active/held/stopped),
        prescriber, dispense details. Distinct from administrations.
        """,
        aliases=("meds", "medList", "medication", "prescriptions", "rx"),
    ),
    PromptEMRDataCategory(
        slug="medicationAdministration",
        name="Medication Administrations (MAR)",
        description="""
        Medication administration record: each administration event with timestamp, dose, route, site,
        rate (for infusions), success/partial/refused, reason, and administering clinician.
        Useful for timing-sensitive questions (e.g., when the last antibiotic dose was given).
        """,
        aliases=("mar", "administrations", "medAdmin", "infusions", "drips"),
    ),
    # — Orders & orderables —
    PromptEMRDataCategory(
        slug="orders",
        name="Orders",
        description="""
        All orderables: medication orders, lab orders, imaging orders, nursing orders (e.g., restraints, wound care),
        diet/NPO, activity, isolation/precautions, devices, consults, therapy referrals, and care directives.
        Include order status (active/pending/completed/canceled), priority, placer, and timestamps.
        """,
        aliases=("cpoe", "physicianOrders", "nursingOrders", "order", "orderSet"),
    ),
    # — Allergies / intolerances —
    PromptEMRDataCategory(
        slug="allergies",
        name="Allergies & Intolerances",
        description="""
        Substance/drug/food/environmental allergies and intolerances with reaction(s), severity, onset,
        status (active/inactive), and source. Include cross-reactivity and desensitization status if present.
        """,
        aliases=("allergy", "intolerances", "drugAllergy", "hypersensitivity"),
    ),
    # — Problem list / diagnoses —
    PromptEMRDataCategory(
        slug="problems",
        name="Problem List & Diagnoses",
        description="""
        Active and historical problems/diagnoses with codes (ICD/SNOMED), onset/resolution dates,
        problem status, and clinical notes/context. Useful for summarizing comorbidities and chronic issues.
        """,
        aliases=("diagnoses", "dx", "problemList", "conditions"),
    ),
    # — Past medical/surgical/family/social history —
    PromptEMRDataCategory(
        slug="pastHistory",
        name="Past Medical & Surgical History",
        description="""
        Prior medical conditions and surgeries/procedures with dates, laterality, complications,
        and brief narratives. Distinct from active problem list to capture historical context.
        """,
        aliases=("pmh", "psh", "history", "medicalHistory", "surgicalHistory"),
    ),
    PromptEMRDataCategory(
        slug="familyHistory",
        name="Family History",
        description="""
        Familial diseases and relevant genetic/inherited risks, relation, age at onset,
        and known testing status for relatives where recorded.
        """,
        aliases=("fhx", "familyHx"),
    ),
    PromptEMRDataCategory(
        slug="socialHistory",
        name="Social History",
        description="""
        Tobacco, alcohol, and substance use; housing/food security; caregiver status; occupation;
        sexual history; exercise; exposure risks; and other SDOH details beyond demographics.
        """,
        aliases=("shx", "socialHx", "sdoh", "lifestyle"),
    ),
    # — Immunizations —
    PromptEMRDataCategory(
        slug="immunizations",
        name="Immunizations",
        description="""
        Vaccination history and due items: vaccine type, lot, manufacturer, dates, series status,
        reactions, and titer evidence where available.
        """,
        aliases=("vaccines", "shots", "imms"),
    ),
    # — Encounters / admissions / locations —
    PromptEMRDataCategory(
        slug="encounters",
        name="Encounters & Admissions",
        description="""
        Encounter timeline including ED visits, inpatient admissions, transfers, discharges, clinic visits,
        location history (unit/bed), lengths of stay, and encounter diagnoses.
        """,
        aliases=("visits", "admissions", "discharges", "encounterHistory"),
    ),
    # — Care team —
    PromptEMRDataCategory(
        slug="careTeam",
        name="Care Team & Providers",
        description="""
        Assigned and involved clinicians: PCP, attending, consultants, covering providers, nurses,
        case managers, and their roles/contact where available.
        """,
        aliases=("providers", "team", "careProviders"),
    ),
    # — Procedures actually performed (separate from order or result) —
    PromptEMRDataCategory(
        slug="procedures",
        name="Procedures Performed",
        description="""
        Procedures completed (bedside and operative): name, date/time, operator, approach,
        devices/implants used, immediate outcome/complications, and links to related reports.
        """,
        aliases=("procedureHistory", "ops", "surgeries"),
    ),
    # — Lines / drains / airways —
    PromptEMRDataCategory(
        slug="linesDrainsAirways",
        name="Lines, Drains, and Airways (LDA)",
        description="""
        Presence and status of central/peripheral lines, arterial lines, chest tubes, surgical drains,
        urinary catheters, tracheostomies, ETTs, and insertion dates with site assessments.
        """,
        aliases=("lda", "lines", "drains", "airways", "catheters", "tubes"),
    ),
    # — Intake & Output —
    PromptEMRDataCategory(
        slug="intakeOutput",
        name="Intake & Output",
        description="""
        Fluid intake and output volumes over intervals, net balance, urine output, drain outputs,
        stool counts, emesis, dialysis ins/outs, and related timestamps.
        """,
        aliases=("io", "i&o", "fluidBalance"),
    ),
    # — Flowsheets & scores —
    PromptEMRDataCategory(
        slug="flowsheets",
        name="Nursing Flowsheets & Scores",
        description="""
        Structured bedside assessments and scales: pain scores, RASS, CAM-ICU, GCS, Braden, fall risk,
        neuro checks, pupil checks, sepsis screens, and other periodic observations.
        """,
        aliases=("flowsheet", "scores", "assessments", "scales"),
    ),
    # — Microbiology (often needs more detail than generic labs) —
    PromptEMRDataCategory(
        slug="microbiology",
        name="Microbiology",
        description="""""
        Culture results with organism IDs, colony counts, Gram stains, susceptibilities/antibiograms,
        and collection/site details (e.g., blood, urine, sputum, wound).
        """,
        aliases=("micro", "cultures", "sensitivities", "antibiogram"),
    ),
    # — Pathology (separate for clarity) —
    PromptEMRDataCategory(
        slug="pathology",
        name="Pathology",
        description="""
        Surgical and cytopathology reports: specimen source, gross/microscopic descriptions,
        diagnoses, margins, staging/grade, and ancillary studies.
        """,
        aliases=("path", "biopsy", "cytology", "surgicalPath"),
    ),
    # — Imaging media/links (not just reports) —
    PromptEMRDataCategory(
        slug="radiologyMedia",
        name="Imaging Media/Links",
        description="""
        Links/references to viewable images (e.g., DICOM, PACS) and key imaging metadata
        (accession, modality, series). Distinct from narrative imaging reports in testResults.
        """,
        aliases=("imaging", "dicom", "pacs", "imageLinks"),
    ),
    # — Genomics / molecular —
    PromptEMRDataCategory(
        slug="genomics",
        name="Genomic & Molecular Data",
        description="""
        Genetic and molecular test results (e.g., tumor panels, germline testing, pharmacogenomics),
        variants, interpretations, and clinical actionability notes.
        """,
        aliases=("genetics", "molecular", "pgx", "precisionMedicine"),
    ),
    # — Risk scores / calculators —
    PromptEMRDataCategory(
        slug="riskScores",
        name="Clinical Scores & Calculators",
        description="""
        System-calculated or documented risk scores and severity indices: CHA₂DS₂-VASc, Wells,
        SOFA/APACHE, MELD, NIHSS, ASCVD risk, and others with component inputs when available.
        """,
        aliases=("scores", "risk", "calculators", "severity"),
    ),
    # — Care plans / goals —
    PromptEMRDataCategory(
        slug="carePlans",
        name="Care Plans, Goals & Pathways",
        description="""
        Interdisciplinary plan of care: goals, interventions, pathways/roadmaps, target dates,
        progress notes, and responsible team members.
        """,
        aliases=("planOfCare", "poc", "goals", "carePathways"),
    ),
    # — Advance directives / code status —
    PromptEMRDataCategory(
        slug="advanceDirectives",
        name="Advance Directives & Code Status",
        description="""
        Code status (e.g., Full, DNR/DNI), POLST/MOLST, health care proxy/surrogate information,
        and limitations of treatment with dates and legal attestations.
        """,
        aliases=("codeStatus", "directives", "polst", "molst"),
    ),
    # — Nutrition / diet —
    PromptEMRDataCategory(
        slug="nutrition",
        name="Nutrition & Diet Orders",
        description="""
        Diet orders (NPO/clear liquid/regular), tube feeds/TPN formulas and rates, nutrition assessments,
        caloric/protein goals, swallow studies recommendations.
        """,
        aliases=("diet", "tpn", "tubeFeeds", "enteral", "parenteral"),
    ),
    # — Respiratory support —
    PromptEMRDataCategory(
        slug="respiratorySupport",
        name="Respiratory Support",
        description="""
        Oxygen delivery and ventilatory support settings: device/mode (e.g., nasal cannula, HFNC, CPAP/BiPAP, invasive ventilation),
        FiO₂, PEEP, rate, tidal volume, and recent changes with timestamps.
        """,
        aliases=("ventilation", "oxygen", "ventSettings", "cpap", "bipap", "hfnc"),
    ),
    # — Wounds / skin —
    PromptEMRDataCategory(
        slug="woundCare",
        name="Wounds & Skin Integrity",
        description="""
        Wound assessments, staging, measurements, photos/diagrams (if referenced), dressings,
        care plans, and healing trajectory. Include pressure injuries and burns.
        """,
        aliases=("wounds", "skin", "pressureInjury", "ulcers", "burns"),
    ),
    # — Therapies & rehabilitation —
    PromptEMRDataCategory(
        slug="therapies",
        name="Therapies & Rehabilitation",
        description="""
        Physical/Occupational/Speech therapy consults, evaluations, treatment plans, progress notes,
        mobility/ADL status, and recommended equipment/precautions.
        """,
        aliases=("pt", "ot", "slp", "rehab", "therapy"),
    ),
    # — Consults & referrals (requests + responses) —
    PromptEMRDataCategory(
        slug="consults",
        name="Consults & Referrals",
        description="""
        Requested and completed consults (e.g., cardiology, ID) with reason for consult, urgency,
        acceptance, timing, and consult note linkage.
        """,
        aliases=("referrals", "specialtyConsults", "consultRequests"),
    ),
    # — Scheduling / follow-ups —
    PromptEMRDataCategory(
        slug="scheduling",
        name="Appointments & Scheduling",
        description="""
        Upcoming and past appointments, scheduled procedures, follow-ups, no-shows/cancellations,
        and instructions/locations.
        """,
        aliases=("appointments", "schedule", "followUp", "bookings"),
    ),
    # — Insurance / billing (often needed for disposition/questions) —
    PromptEMRDataCategory(
        slug="insurance",
        name="Insurance & Coverage",
        description="""
        Payer/plan details, coverage periods, authorizations, copays/deductibles, and financial counseling notes
        relevant to care planning and discharge.
        """,
        aliases=("coverage", "payer", "benefits", "guarantor"),
    ),
    PromptEMRDataCategory(
        slug="billing",
        name="Billing & Coding",
        description="""
        Charge capture, CPT/HCPCS/ICD codes, DRGs, and claims status where available for clinical/operational questions.
        """,
        aliases=("coding", "charges", "claims", "revenueCycle"),
    ),
    # — Communication / consents / education —
    PromptEMRDataCategory(
        slug="communications",
        name="Patient Communications & Messages",
        description="""
        Secure messages/portal threads, documented phone calls, and other communication logs
        that may impact clinical decisions (e.g., symptom updates, instructions given).
        """,
        aliases=("messages", "portal", "inbox", "callLogs"),
    ),
    PromptEMRDataCategory(
        slug="consents",
        name="Consents & Authorizations",
        description="""
        Documented informed consents and authorizations covering procedures, blood products,
        anesthesia, data sharing, and research participation.
        """,
        aliases=("consent", "authorizations", "permissions"),
    ),
    PromptEMRDataCategory(
        slug="patientEducation",
        name="Patient Education",
        description="""
        Education materials provided, teach-back documentation, learning barriers, and readiness,
        including language and interpreter use.
        """,
        aliases=("education", "teaching", "educationNotes"),
    ),
)

_CLASSIFIER_TEMPLATE = """
You are an expert curator for an electronic health record (EHR) prompt library.

Select every category slug from the allowed list that indicates data from the EMR 
that would be required to answer or satisfy the prompt.
Use only the slugs listed below and respond with a JSON array of slugs. If none apply,
respond with an empty array ``[]``. Do not invent new categories.

Allowed categories (slug – name – description):
{category_overview}

Structured category metadata:
{category_json}

Prompt metadata (JSON):
{prompt_json}
""".strip()

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[[^\]]*\]", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{[^\}]*\}", re.DOTALL)


def _normalize_token(value: str) -> str:
    token = re.sub(r"[^0-9a-zA-Z]+", "_", value.strip().lower())
    return token.strip("_")


def _deduplicate_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _build_alias_map(categories: Sequence[PromptEMRDataCategory]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category in categories:
        for candidate in (category.slug, category.name, *category.aliases):
            normalized = _normalize_token(candidate)
            if not normalized:
                continue
            mapping[normalized] = category.slug
    return mapping


def _render_category_overview(categories: Sequence[PromptEMRDataCategory]) -> str:
    lines: list[str] = []
    for category in categories:
        alias_text = ""
        if category.aliases:
            alias_text = f" (aliases: {', '.join(category.aliases)})"
        lines.append(
            f"- {category.slug} – {category.name}{alias_text}: {category.description}"
        )
    return "\n".join(lines)


def _render_category_json(categories: Sequence[PromptEMRDataCategory]) -> str:
    payload = [category.as_dict() for category in categories]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _strip_code_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def _candidate_json_fragments(text: str) -> list[str]:
    stripped = _strip_code_fence(text)
    if not stripped:
        return []
    candidates = [stripped]
    candidates.extend(match.group(0) for match in _JSON_ARRAY_RE.finditer(stripped))
    candidates.extend(match.group(0) for match in _JSON_OBJECT_RE.finditer(stripped))
    return _deduplicate_preserve_order(candidates)


def _iter_possible_values(payload: Any) -> Iterable[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        explicit = payload.get("slug") or payload.get("id") or payload.get("name")
        if isinstance(explicit, str):
            return [explicit]
        for key in ("categories", "labels", "values", "tags"):
            if key in payload:
                return _iter_possible_values(payload[key])
        return []
    if isinstance(payload, Iterable):
        results: list[str] = []
        for item in payload:
            results.extend(_iter_possible_values(item))
        return results
    return [str(payload)]


class CategoryClassifier:
    """Wrapper around a :class:`LLMChain` for prompt categorization."""

    def __init__(
        self, chain: LLMChain, categories: Sequence[PromptEMRDataCategory]
    ) -> None:
        self._chain = chain
        self._categories = tuple(categories)
        self._alias_map = _build_alias_map(self._categories)

    @classmethod
    def create(
        cls, llm: Any, categories: Sequence[PromptEMRDataCategory] | None = None
    ) -> "CategoryClassifier":
        """Create a classifier bound to ``llm`` and the provided ``categories``."""

        selected = tuple(categories or DEFAULT_PROMPT_CATEGORIES)
        prompt = PromptTemplate.from_template(_CLASSIFIER_TEMPLATE).partial(
            category_overview=_render_category_overview(selected),
            category_json=_render_category_json(selected),
        )
        chain = LLMChain(llm=llm, prompt=prompt, output_key="categories")
        return cls(chain, selected)

    @property
    def chain(self) -> LLMChain:
        """Return the underlying :class:`LLMChain`."""

        return self._chain

    @property
    def categories(self) -> tuple[PromptEMRDataCategory, ...]:
        """Return the known categories used by the classifier."""

        return self._categories

    def parse_response(self, text: str) -> list[str]:
        """Parse ``text`` into a list of canonical category slugs."""

        stripped = text.strip()
        if not stripped:
            return []

        for candidate in _candidate_json_fragments(stripped):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            resolved = self._extract_slugs(payload)
            if resolved:
                return resolved

        return self._parse_fallback(stripped)

    def _extract_slugs(self, payload: Any) -> list[str]:
        values = _iter_possible_values(payload)
        resolved: list[str] = []
        for value in values:
            slug = self._resolve_slug(value)
            if slug:
                resolved.append(slug)
        return _deduplicate_preserve_order(resolved)

    def _parse_fallback(self, text: str) -> list[str]:
        tokens = re.split(r"[,\n]+", text)
        resolved: list[str] = []
        for token in tokens:
            slug = self._resolve_slug(token)
            if slug:
                resolved.append(slug)
        return _deduplicate_preserve_order(resolved)

    def _resolve_slug(self, value: str) -> str | None:
        normalized = _normalize_token(value)
        if not normalized:
            return None
        return self._alias_map.get(normalized)
