"""Reporting helpers for the anonymizer service."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping


def summarize_transformations(
    transformations: Iterable[Mapping[str, Any]]
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
            transformation counts and the distribution of anonymization
            actions.
    """

    total = 0
    action_counts: Counter[str] = Counter()
    entity_stats: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "actions": Counter()}
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

    return {
        "total_transformations": total,
        "actions": dict(sorted(action_counts.items())),
        "entities": {
            entity: {
                "count": stats["count"],
                "actions": dict(sorted(stats["actions"].items())),
            }
            for entity, stats in sorted(entity_stats.items())
        },
    }


__all__ = ["summarize_transformations"]

