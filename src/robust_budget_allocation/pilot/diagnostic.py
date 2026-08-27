"""One authorized EF diagnostic, never a resume or a scientific paired group."""

import json
from pathlib import Path

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.io.locking import exclusive_file_lock
from .configuration import ROOT, SCOPE
from .execution import run_one, source_gate, utc
from .replay import load_bundle, replay_run
from .storage import read_run, retry_lineage, seal, check_seal

PARENT_BATCH = "n6pilot01"
PARENT_ID = "n6pilot01-00-ef"
BATCH = "n6diagnostic01"
RUN_ID = "n6diagnostic01-ef-retry"
REASON = "supervisor heartbeat I/O diagnostic after approved harness repair"
AUTHORIZATION = "docs/N6_HARNESS_REPAIR_AUTHORIZATION.md"
PARENT_ARCHIVE = "docs/evidence/N6_PILOT_EVIDENCE.json.gz"
PARENT_ARCHIVE_SHA = "ba8b56a1c586365cc802463897b7ba2a4d55c6de378751df636ae47990f3aecd"


def claim_once(pilot_root, source):
    """The authorization is consumed before launch, including crash/failure paths."""
    pilot_root = Path(pilot_root)
    with exclusive_file_lock(pilot_root / ".locks/n6-ef-diagnostic-authorization.lock", timeout_seconds=0):
        path = pilot_root / ".authorizations/n6-ef-diagnostic-once.json"
        if path.exists() or (pilot_root / BATCH).exists():
            raise FileExistsError("single diagnostic authorization already consumed")
        claim = seal(dict(kind="single_diagnostic_retry", claimed_utc=utc(), batch=BATCH, run_id=RUN_ID,
            parent_batch_id=PARENT_BATCH, parent_run_id=PARENT_ID, retry_reason=REASON,
            method="EF", purpose="harness_diagnostic_only", source=source,
            authorization_path=AUTHORIZATION, authorization_sha256=sha256_file(ROOT / AUTHORIZATION)))
        atomic_write_json(path, claim)
        return claim


def diagnostic_retry():
    pilot_root = ROOT / "outputs/pilot"
    before = source_gate()  # immutable code commit required
    if sha256_file(ROOT / PARENT_ARCHIVE) != PARENT_ARCHIVE_SHA:
        raise ValueError("original parent evidence changed")
    frozen_parent = next(run for run in load_bundle(ROOT / PARENT_ARCHIVE)["runs"]
                         if json.loads(run["files"]["record.json"])["run_id"] == PARENT_ID)
    lineage, saved_parent = retry_lineage(pilot_root / BATCH, PARENT_BATCH, PARENT_ID)
    if saved_parent != frozen_parent:
        raise ValueError("original parent directory differs from reviewed evidence")
    decoded = replay_run(saved_parent)
    if decoded["record"]["status"] != "incomplete" or decoded["record"]["method"] != "EF":
        raise ValueError("only original failed EF is authorized")
    request = json.loads(saved_parent["files"]["request.json"])
    claim = claim_once(pilot_root, before)
    folder = pilot_root / BATCH / RUN_ID
    try:
        run_one(pilot_root / BATCH, RUN_ID, request["config"], "EF", parent_run_id=PARENT_ID,
                parent_batch_id=PARENT_BATCH, retry_reason=REASON, purpose="harness_diagnostic_only")
    except KeyboardInterrupt:
        pass  # run_one sealed the interruption; preserve and stop, never rerun
    retry = read_run(folder)
    after = source_gate()
    if any(before[k] != after[k] for k in ("commit_sha", "tree_sha")):
        raise RuntimeError("source changed during diagnostic")
    # Immutable parent check again: no writes/resume into the old batch.
    if read_run(pilot_root / PARENT_BATCH / PARENT_ID) != frozen_parent:
        raise ValueError("parent changed during diagnostic")
    evidence = seal(dict(schema_version=1, kind="single_diagnostic_retry", classification=SCOPE,
        authorization_claim=claim, parent=saved_parent, retry=retry, lineage=lineage,
        source_gate=before, original_parent_archive_sha256=PARENT_ARCHIVE_SHA,
        scientific_group=False, paired_runs=0, full_pilot_resume_authorized=False,
        n7_authorized=False), "evidence_sha256")
    return folder.parent, evidence


def replay_diagnostic(evidence):
    check_seal(evidence, "evidence_sha256")
    if evidence["kind"] != "single_diagnostic_retry" or evidence["classification"] != SCOPE:
        raise ValueError("diagnostic scope")
    if evidence["scientific_group"] is not False or evidence["paired_runs"] != 0 or (
            evidence["full_pilot_resume_authorized"] is not False or evidence["n7_authorized"] is not False):
        raise ValueError("diagnostic cannot authorize scientific resumption")
    claim = evidence["authorization_claim"]
    check_seal(claim)
    expected = dict(parent_run_id=PARENT_ID, parent_batch_id=PARENT_BATCH, run_id=RUN_ID,
                    batch=BATCH, retry_reason=REASON, method="EF", purpose="harness_diagnostic_only")
    if any(claim[k] != v for k, v in expected.items()):
        raise ValueError("unauthorized retry claim")
    if claim["authorization_sha256"] != sha256_file(ROOT / AUTHORIZATION):
        raise ValueError("authorization document changed")
    if claim["source"] != evidence["source_gate"]:
        raise ValueError("claim/source gate")
    if evidence["original_parent_archive_sha256"] != PARENT_ARCHIVE_SHA or sha256_file(ROOT / PARENT_ARCHIVE) != PARENT_ARCHIVE_SHA:
        raise ValueError("original archive binding")
    original = next(run for run in load_bundle(ROOT / PARENT_ARCHIVE)["runs"]
                    if json.loads(run["files"]["record.json"])["run_id"] == PARENT_ID)
    if evidence["parent"] != original:
        raise ValueError("embedded parent is not reviewed failure")
    parent, retry = replay_run(evidence["parent"]), replay_run(evidence["retry"])
    p, r = parent["record"], retry["record"]
    for key, value in expected.items():
        if key != "batch" and r.get(key) != value:
            raise ValueError("retry lineage field: "+key)
    if r["binding"] != p["binding"] or r["method"] != p["method"]:
        raise ValueError("retry changes input/config/scenario")
    lineage = dict(parent_batch_id=PARENT_BATCH, parent_run_id=PARENT_ID,
        parent_relative_path=PARENT_BATCH+"/"+PARENT_ID, parent_output_sha256=p["output_sha256"],
        parent_manifest_sha256=evidence["parent"]["manifest"]["sha256"],
        parent_commit_sha=p["source"]["git"]["commit_sha"], parent_tree_sha=p["source"]["git"]["tree_sha"])
    if r["lineage"] != lineage or evidence["lineage"] != lineage:
        raise ValueError("parent source/hash lineage")
    if any(r["source"]["git"][k] != evidence["source_gate"][k] for k in ("commit_sha", "tree_sha")):
        raise ValueError("retry execution source gate")
    return dict(diagnostic_status="PASS" if retry["replay"] == "PASS" else "FAIL",
                run_id=RUN_ID, parent_run_id=PARENT_ID, run_status=r["status"],
                parent_status=p["status"], scientific_group=False, paired_runs=0,
                n6_stage_complete=False, n7_authorized=False)

