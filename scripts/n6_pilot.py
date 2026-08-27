"""N6-only bounded pilot: registered matrix, isolated runs, compact audit archive."""

import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import sha256_file
from robust_budget_allocation.io.locking import exclusive_file_lock
from robust_budget_allocation.pilot.configuration import (
    CONFIG_SHA, PROTOCOL_SHA, SCOPE, registration, execution_order)
from robust_budget_allocation.pilot.execution import worker, run_one, source_gate
from robust_budget_allocation.pilot.storage import safe_id, read_run, seal
from robust_budget_allocation.pilot.replay import replay_bundle, replay_group, load_bundle
from robust_budget_allocation.pilot.summary import summarize


def archive(path, payload):
    """Binary compact artifact, atomic replace with no overwrite permission."""
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = gzip.compress(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":"), allow_nan=False).encode("utf-8"), mtime=0)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".n6-", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        # Caller holds the batch lease; destination existence is checked again.
        if path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def execute(batch):
    safe_id(batch)
    reg = registration()
    before = source_gate()
    root = ROOT / "outputs/pilot" / batch
    with exclusive_file_lock(ROOT / "outputs/pilot/.locks" / (batch+".lock"), timeout_seconds=0):
        root.mkdir(parents=True, exist_ok=False)
        runs, pair_checks, failure = [], {}, None
        for index, config in enumerate(reg["configs"]):
            group = []
            for method in execution_order(index):
                run_id = f"{batch}-{index:02d}-{method.lower()}"
                folder = run_one(root, run_id, config, method)
                saved = read_run(folder)
                runs.append(saved)
                group.append(saved)
                record = json.loads(saved["files"]["record.json"])
                print(json.dumps(dict(run_id=run_id, config_id=config["id"], method=method,
                                      status=record["status"], metrics=record["metrics"])), flush=True)
                if record["status"] != "success/certified":
                    failure = dict(run_id=run_id, status=record["status"])
                    break
            if failure is not None:
                break
            try:
                pair_checks[config["id"]] = replay_group(group)
            except Exception as exc:
                failure = dict(config_id=config["id"], status="verification_failure", diagnostic=repr(exc))
                break  # correctness STOP, never repair/retry frozen code here
        after = source_gate()
        if any(before[k] != after[k] for k in ("commit_sha", "tree_sha")):
            failure = dict(status="verification_failure", diagnostic="execution source changed")
        bundle = seal(dict(schema_version=1, classification=SCOPE, protocol_sha256=PROTOCOL_SHA,
            config_sha256=CONFIG_SHA, source_gate=before, batch_id=batch, runs=runs,
            status="PASS" if failure is None and len(runs) == 80 else "FAIL",
            failure=failure, pair_checks=pair_checks), "evidence_sha256")
        destination = root / "compact_evidence.json.gz"
        archive(destination, bundle)
        summary = summarize(bundle)
        atomic_write_json(root / "summary.json", summary)
        if failure is None:
            print(json.dumps(replay_bundle(bundle)), flush=True)
        print(json.dumps(dict(state=summary["state"], evidence=str(destination),
                              sha256=sha256_file(destination), failure=failure)), flush=True)
        return 0 if failure is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "worker", "replay", "summarize"))
    parser.add_argument("--batch")
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if args.action == "run":
        return execute(args.batch)
    if args.action == "worker":
        if args.folder is None or not args.folder.resolve().is_relative_to((ROOT / "outputs/pilot").resolve()):
            raise ValueError("worker must operate under outputs/pilot")
        return worker(args.folder)
    bundle = load_bundle(args.evidence)
    result = replay_bundle(bundle) if args.action == "replay" else summarize(bundle)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

