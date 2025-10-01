"""Reporting helpers for the anonymizer service."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, MutableMapping


def _extract_note_count(metadata: Any) -> int:
    """Return the number of metadata notes without exposing their content."""

    if isinstance(metadata, Mapping):
        metadata = metadata.get("notes")

    if metadata is None:
        return 0

    if isinstance(metadata, str):
        # Treat a non-empty string as a single note.  Strings are iterables of
        # characters which would otherwise inflate the count.
        return int(bool(metadata.strip()))

    try:
        iterator = iter(metadata)
    except TypeError:
        return 0

    count = 0
    for _ in iterator:
        count += 1
    return count


def summarize_transformations(
    transformations: Iterable[Mapping[str, Any]],
    generalization_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate anonymization transformations into a JSON friendly summary.

    The anonymizer may record individual transformation events that include
    sensitive values such as the original piece of PHI.  This helper collapses
    those events into high level counts grouped by entity type and action
    ensuring that the returned payload is JSON serializable and does not
    include any raw PHI strings.

    Parameters
    ----------
    transformations:
        Iterable of mapping-like records describing the transformations that
        were applied.  Each record is expected to expose an ``entity_type`` (or
        ``entity``) field describing the identified Presidio entity and an
        ``action`` (or ``strategy``) field describing how the entity was
        anonymized.

        generalization_metadata:
            Optional mapping keyed by entity type providing additional
            anonymization metadata.  Only the count of ``notes`` entries is
            surfaced in the returned summary to avoid exposing PHI.

    Returns
    -------
    dict[str, Any]
        Summary dictionary with keys:

        ``total_transformations``
            Total number of transformations encountered.

        ``actions``
            Mapping of action name to the number of occurrences.

        ``entities``
            Nested mapping keyed by entity type containing the per-entity
            transformation counts, the distribution of anonymization actions,
            and the ``notes_count`` derived from any supplied metadata.
    """

    total = 0
    action_counts: Counter[str] = Counter()
    entity_stats: defaultdict[str, MutableMapping[str, Any]] = defaultdict(
        lambda: {"count": 0, "actions": Counter(), "notes_count": 0}
    )

    for record in transformations:
        if not isinstance(record, Mapping):
            continue

        entity = record.get("entity_type") or record.get("entity") or "UNKNOWN"
        action = record.get("action") or record.get("strategy") or "unknown"

        entity = str(entity)
        action = str(action)

        total += 1
        action_counts[action] += 1
        entity_stats[entity]["count"] += 1
        entity_stats[entity]["actions"][action] += 1

    metadata: Mapping[str, Any] = generalization_metadata or {}
    if isinstance(metadata, Mapping):
        for entity, info in metadata.items():
            entity_key = str(entity)
            if entity_key not in entity_stats:
                continue

            note_count = _extract_note_count(info)
            entity_stats[entity_key]["notes_count"] = note_count

    return {
        "total_transformations": total,
        "actions": dict(sorted(action_counts.items())),
        "entities": {
            entity: {
                "count": stats["count"],
                "actions": dict(sorted(stats["actions"].items())),
                "notes_count": stats.get("notes_count", 0),
            }
            for entity, stats in sorted(entity_stats.items())
        },
    }


__all__ = ["summarize_transformations"]

