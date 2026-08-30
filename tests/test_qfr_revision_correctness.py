from copy import deepcopy
import json
from pathlib import Path

import pytest

from robust_budget_allocation.algorithms.qfr_revision_suite import (
    load_revision_fixture,
    validate_revision_evidence,
)
from robust_budget_allocation.data.qfr_data import QFRData
from robust_budget_allocation.io.hashing import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/qfr_availability_correctness_v2_1.json"


def reseal(evidence):
    evidence["evidence_sha256"] = canonical_json_sha256(
        {key: value for key, value in evidence.items() if key != "evidence_sha256"}
    )


def test_revision_fixture_is_small_correctness_only_and_complete():
    payload = load_revision_fixture(FIXTURE)
    assert payload["fixture_scope"] == "CORRECTNESS_FIXTURE_ONLY_NOT_PILOT_OR_FORMAL_PARAMETERS"
    data = QFRData.from_dict(payload["cases"][0]["data"])
    assert data.schema_version == 3
    assert len(data.items) == 3
    assert any(
        data.q_availability[scenario][item] < 1
        for scenario in data.scenarios
        for item in data.items
    )


def test_revision_fixture_rejects_pre_revision_schema(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data = payload["cases"][0]["data"]
    data["schema_version"] = 2
    del data["q_availability"]
    for item in data["items"]:
        data["reliability_mitigation"][item]["0"] = 0.0
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version 3"):
        load_revision_fixture(path)


def test_revision_evidence_rejects_q_availability_substitution_if_present():
    evidence_path = ROOT / "docs/evidence/QFR_AVAILABILITY_CORRECTNESS_FIRST_RUN_v2_1.json"
    if not evidence_path.exists():
        pytest.skip("revised licensed evidence is created only after clean execution commit")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    changed = deepcopy(evidence)
    changed["fixture"]["payload"]["cases"][0]["data"]["q_availability"]["b_medium"]["ordinary"] = 0.8
    reseal(changed)
    with pytest.raises(ValueError, match="fixture identity"):
        validate_revision_evidence(ROOT, changed)
