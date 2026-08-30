"""Generic solve-local exact-evaluation history for R4 A1."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Iterable, Mapping


CAPACITY = 8
MAX_AGE = 4
INSPECTION_LIMIT = 2
SOURCES = frozenset({"MEMORY", "CANDIDATE", "EXACT"})


class QFRScenarioMemory:
    def __init__(self, data_sha256: str, identities: Mapping[str, str]) -> None:
        self.data_sha256 = data_sha256
        self.identities = dict(identities)
        self._entries: dict[str, dict[str, Any]] = {}

    def snapshot(self) -> list[dict[str, Any]]:
        return [deepcopy(self._entries[key]) for key in sorted(self._entries)]

    def prune(self, iteration: int) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        required = {
            "scenario_id",
            "scenario_identity",
            "data_sha256",
            "last_loss",
            "last_iteration",
            "last_source",
        }
        for scenario in sorted(self._entries):
            entry = self._entries[scenario]
            reason = None
            if scenario not in self.identities:
                reason = "unknown_scenario"
            elif not isinstance(entry, dict) or set(entry) != required:
                reason = "malformed_entry"
            elif (
                entry["scenario_id"] != scenario
                or entry["scenario_identity"] != self.identities[scenario]
                or entry["data_sha256"] != self.data_sha256
            ):
                reason = "identity_mismatch"
            elif (
                isinstance(entry["last_loss"], bool)
                or not isinstance(entry["last_loss"], (int, float))
                or not math.isfinite(entry["last_loss"])
                or entry["last_loss"] < 0
            ):
                reason = "invalid_loss"
            elif (
                type(entry["last_iteration"]) is not int
                or entry["last_iteration"] < 1
                or entry["last_iteration"] >= iteration
            ):
                reason = "invalid_iteration"
            elif entry["last_source"] not in SOURCES:
                reason = "invalid_source"
            elif iteration - entry["last_iteration"] > MAX_AGE:
                reason = "stale"
            if reason is not None:
                removed.append(
                    {"scenario_id": scenario, "reason": reason, "entry": deepcopy(entry)}
                )
        for row in removed:
            del self._entries[row["scenario_id"]]
        return removed

    def inspection_plan(self, active: Iterable[str]) -> dict[str, Any]:
        active_set = set(active)
        skipped = sorted(scenario for scenario in self._entries if scenario in active_set)
        eligible = [
            entry for scenario, entry in self._entries.items() if scenario not in active_set
        ]
        ranking = sorted(
            eligible,
            key=lambda entry: (
                -float(entry["last_loss"]),
                -int(entry["last_iteration"]),
                str(entry["scenario_id"]),
            ),
        )
        return {
            "skipped_active": skipped,
            "ranking": [deepcopy(entry) for entry in ranking],
            "planned": [entry["scenario_id"] for entry in ranking[:INSPECTION_LIMIT]],
        }

    def update(
        self,
        rows: Iterable[Mapping[str, Any]],
        iteration: int,
        source: str,
    ) -> dict[str, Any]:
        if source not in SOURCES or type(iteration) is not int or iteration <= 0:
            raise ValueError("invalid A1 memory update provenance")
        updated: list[str] = []
        for row in rows:
            scenario = str(row["scenario_id"])
            loss = float(row["loss"])
            if (
                scenario not in self.identities
                or row["scenario_identity"] != self.identities[scenario]
                or row["solver"]["status"] != "optimal"
                or not math.isfinite(loss)
                or loss < 0
            ):
                raise ValueError("only valid exact evaluations may enter A1 memory")
            self._entries[scenario] = {
                "scenario_id": scenario,
                "scenario_identity": self.identities[scenario],
                "data_sha256": self.data_sha256,
                "last_loss": loss,
                "last_iteration": iteration,
                "last_source": source,
            }
            updated.append(scenario)
        retained = sorted(
            self._entries.values(),
            key=lambda entry: (
                -int(entry["last_iteration"]),
                -float(entry["last_loss"]),
                str(entry["scenario_id"]),
            ),
        )
        evicted = deepcopy(retained[CAPACITY:])
        self._entries = {
            str(entry["scenario_id"]): entry for entry in retained[:CAPACITY]
        }
        return {"updated": updated, "evicted": evicted}
