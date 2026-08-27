"""Immutable pilot run IDs, N1 leases/atomic I/O and exact hash inventories."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from robust_budget_allocation.io.atomic import atomic_write_json
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.io.locking import exclusive_file_lock

RUN_FILES = frozenset(("request.json", "heartbeat.json", "result.json", "record.json",
                       "stdout.txt", "stderr.txt"))
FAILURE_STATES = frozenset(("solver_error", "infeasible", "unbounded", "time_limit",
    "iteration_limit", "numerical_failure", "oracle_failure", "verification_failure",
    "interrupted", "incomplete"))


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}", value):
        raise ValueError("unsafe run ID")
    return value


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("unsafe manifest path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in value.split("/") or str(path) != value:
        raise ValueError("unsafe manifest path")
    return value


def normalize_failure(status):
    if status in ("optimal", "certified"):
        return "success/certified"
    if status in FAILURE_STATES:
        return status
    return {"numerical_invalid": "numerical_failure",
            "convergence_failure": "verification_failure"}.get(status, "solver_error")


def seal(payload, key="sha256"):
    result = dict(payload)
    if key in result:
        raise ValueError("self hash already present")
    result[key] = canonical_json_sha256(result)
    return result


def check_seal(payload, key="sha256"):
    bare = {k: v for k, v in payload.items() if k != key}
    if payload.get(key) != canonical_json_sha256(bare):
        raise ValueError("self hash mismatch: " + key)


@contextmanager
def reserve(root, run_id, *, parent_run_id=None, retry_reason=None):
    safe_id(run_id)
    if (parent_run_id is None) != (retry_reason is None):
        raise ValueError("retry requires parent and reason")
    if parent_run_id is not None:
        safe_id(parent_run_id)
        if parent_run_id == run_id or not isinstance(retry_reason, str) or not retry_reason.strip():
            raise ValueError("invalid retry")
        parent = root / parent_run_id / "record.json"
        if not parent.is_file():
            raise ValueError("missing parent run")
        original = json.loads(parent.read_text(encoding="utf-8"))
        check_seal(original, "output_sha256")
        if original["status"] == "success/certified":
            raise ValueError("cannot retry a successful run")
    with exclusive_file_lock(root / ".locks" / (run_id + ".lock"), timeout_seconds=0):
        target = root / run_id
        target.mkdir(parents=True, exist_ok=False)
        yield target


def file_manifest(folder):
    entries = []
    for name in sorted(RUN_FILES):
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing/nonregular run file: " + name)
        entries.append(dict(path=name, sha256=sha256_file(path), bytes=path.stat().st_size))
    manifest = seal(dict(schema_version=1, files=entries,
                         external_anchor="record.json source commit/tree; manifest excludes itself"))
    atomic_write_json(folder / "manifest.json", manifest)
    return manifest


def verify_inventory(manifest, files):
    check_seal(manifest)
    entries = manifest["files"]
    names = [safe_relative(e["path"]) for e in entries]
    if len(names) != len(set(names)) or set(names) != RUN_FILES or set(files) != RUN_FILES:
        raise ValueError("run inventory mismatch")
    for entry in entries:
        content = files[entry["path"]].encode("utf-8")
        if entry["bytes"] != len(content) or entry["sha256"] != hashlib.sha256(content).hexdigest():
            raise ValueError("run file hash mismatch")


def read_run(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    files = {}
    for name in RUN_FILES:
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("nonregular file")
        files[name] = path.read_bytes().decode("utf-8")
    actual = {p.name for p in folder.iterdir()}
    if actual != RUN_FILES | {"manifest.json"}:
        raise ValueError("unmanifested run artifact")
    verify_inventory(manifest, files)
    return dict(manifest=manifest, files=files)


def inspect_run(folder):
    """Read-only resume: never overwrite, rerun or reinterpret partial output."""
    if not (folder / "record.json").is_file():
        return "interrupted" if (folder / "heartbeat.json").exists() else "incomplete"
    try:
        bundle = read_run(folder)
        record = json.loads(bundle["files"]["record.json"])
        check_seal(record, "output_sha256")
        return record["status"]
    except (ValueError, OSError, KeyError):
        return "incomplete"

