"""Model-independent deterministic Candidate Search for R4 A1."""

from __future__ import annotations

from typing import Any, Iterable

from robust_budget_allocation.data.qfr_data import QFRData
from .qfr_protocol import canonical_scenarios


EVALUATION_LIMIT = 1


def candidate_plan(
    data: QFRData,
    active: Iterable[str],
    inspected: Iterable[str],
) -> dict[str, Any]:
    active_set, inspected_set = set(active), set(inspected)
    pool: list[str] = []
    excluded: list[dict[str, str]] = []
    for scenario in canonical_scenarios(data):
        reason = (
            "active"
            if scenario in active_set
            else "already_inspected"
            if scenario in inspected_set
            else None
        )
        if reason is None:
            pool.append(scenario)
        else:
            excluded.append({"scenario_id": scenario, "reason": reason})
    return {
        "pool": pool,
        "excluded": excluded,
        "ranking": list(pool),
        "planned": pool[:EVALUATION_LIMIT],
        "ranking_rule": "CANONICAL_SCENARIO_ID_ONLY",
    }
