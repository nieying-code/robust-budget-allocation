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
from robust_budget_allocation.pilot.execution import worker
from robust_budget_allocation.pilot.replay import replay_bundle, load_bundle
from robust_budget_allocation.pilot.diagnostic import diagnostic_retry, replay_diagnostic
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
    from robust_budget_allocation.pilot.restart import execute as restart_execute
    return restart_execute(batch, archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "worker", "replay", "summarize", "diagnostic-retry", "restart-gates"))
    parser.add_argument("--batch")
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if args.action == "diagnostic-retry":
        raise PermissionError("N6_DIAGNOSTIC_RETRY_NOT_AUTHORIZED")
    if args.action == "restart-gates":
        from robust_budget_allocation.pilot.restart import gates
        return gates()
    if args.action == "run":
        return execute(args.batch)
    if args.action == "diagnostic-retry":
        if any((args.batch, args.folder, args.evidence)):
            raise ValueError("diagnostic scope is fixed; no batch/config overrides")
        folder, evidence = diagnostic_retry()
        archive(folder / "compact_retry.json.gz", evidence)
        result = replay_diagnostic(evidence)
        atomic_write_json(folder / "diagnostic_summary.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["diagnostic_status"] == "PASS" else 1
    if args.action == "worker":
        if args.folder is None or not args.folder.resolve().is_relative_to((ROOT / "outputs/pilot").resolve()):
            raise ValueError("worker must operate under outputs/pilot")
        return worker(args.folder)
    bundle = load_bundle(args.evidence)
    if bundle.get("kind") == "single_diagnostic_retry":
        result = replay_diagnostic(bundle)
    else:
        if bundle.get("batch_id") == "n6pilot02" and args.action == "replay":
            from robust_budget_allocation.pilot.restart import replay_restart
            result = replay_restart(bundle)
        else:
            result = replay_bundle(bundle) if args.action == "replay" else summarize(bundle)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
