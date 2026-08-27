"""Bounded, solve-local exact-evaluation history; never an optimality certificate."""

from copy import deepcopy
import math

CAPACITY = 8
MAX_AGE = 4
INSPECTION_LIMIT = 2
SOURCES = frozenset({"MEMORY", "CANDIDATE", "EXACT"})


class ScenarioMemory:
    def __init__(self, data_sha256, scenarios):
        self.data_sha256 = data_sha256
        self.scenarios = frozenset(scenarios)
        self._entries = {}

    def snapshot(self):
        return [deepcopy(self._entries[w]) for w in sorted(self._entries)]

    def prune(self, iteration):
        removed = []
        for w in sorted(self._entries):
            entry = self._entries[w]
            reason = None
            if w not in self.scenarios:
                reason = "unknown_scenario"
            elif not isinstance(entry, dict) or set(entry) != {"scenario", "data_sha256", "last_loss", "last_iteration", "last_source"}:
                reason = "malformed_entry"
            elif entry["scenario"] != w or entry["data_sha256"] != self.data_sha256:
                reason = "identity_mismatch"
            elif isinstance(entry["last_loss"], bool) or not isinstance(entry["last_loss"], (int, float)) or not math.isfinite(entry["last_loss"]) or entry["last_loss"] < 0:
                reason = "invalid_loss"
            elif type(entry["last_iteration"]) is not int or entry["last_iteration"] < 1 or entry["last_iteration"] >= iteration:
                reason = "invalid_iteration"
            elif not isinstance(entry["last_source"], str) or entry["last_source"] not in SOURCES:
                reason = "invalid_source"
            elif iteration-entry["last_iteration"] > MAX_AGE:
                reason = "stale"
            if reason:
                removed.append(dict(scenario=w, reason=reason, entry=deepcopy(entry)))
        for item in removed:
            del self._entries[item["scenario"]]
        return removed

    def inspection_plan(self, active):
        skipped = [w for w in sorted(self._entries) if w in active]
        eligible = [entry for w, entry in self._entries.items() if w not in active]
        ranked = sorted(eligible, key=lambda e: (-e["last_loss"], -e["last_iteration"], e["scenario"]))
        return dict(skipped_active=skipped, ranking=[deepcopy(e) for e in ranked],
                    planned=[e["scenario"] for e in ranked[:INSPECTION_LIMIT]])

    def update(self, rows, iteration, source):
        if source not in SOURCES or type(iteration) is not int or iteration <= 0:
            raise ValueError("invalid memory update provenance")
        updated = []
        for row in rows:
            w, loss = row["scenario"], row["loss"]
            if w not in self.scenarios or row["status"] != "optimal" or not math.isfinite(loss) or loss < 0:
                raise ValueError("only valid exact evaluations may enter memory")
            self._entries[w] = dict(scenario=w, data_sha256=self.data_sha256,
                                    last_loss=loss, last_iteration=iteration, last_source=source)
            updated.append(w)
        retained = sorted(self._entries.values(), key=lambda e: (-e["last_iteration"], -e["last_loss"], e["scenario"]))
        evicted = deepcopy(retained[CAPACITY:])
        self._entries = {e["scenario"]: e for e in retained[:CAPACITY]}
        return dict(updated=updated, evicted=evicted)
