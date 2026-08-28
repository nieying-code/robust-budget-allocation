"""Complete source proofs and immutable serialization for N7-pre, including shallow replay."""

import base64
import gzip
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET

from robust_budget_allocation.io.atomic import _temporary_path, _replace_with_retry, _cleanup
from robust_budget_allocation.io.hashing import canonical_json_bytes, sha256_file
from robust_budget_allocation.reproducibility.git_state import validate_source_state
from robust_budget_allocation.reproducibility.manifests import build_source_manifest
from robust_budget_allocation.pilot.source_archive import object_id, walk_tree
from robust_budget_allocation.pilot.storage import check_seal, safe_relative
from .configuration import ROOT, FROZEN

FIXED = set(FROZEN) | {"scripts/n7_pre.py", "pyproject.toml", "requirements.txt",
                       "docs/N4_CORRECTNESS_PROTOCOL.md", "docs/N5_A1_PROTOCOL.md"}


def same(left, right):
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def selected(entries):
    return FIXED | {p for p in entries if p.startswith("src/robust_budget_allocation/") and p.endswith(".py")}


def inputs():
    return sorted([*ROOT.glob("src/robust_budget_allocation/**/*.py"), *[ROOT / p for p in FIXED]])


def source():
    validate_source_state(ROOT, required_tracked_paths=inputs(), scientific_roots=("src", "tests", "scripts", "configs"))
    return json.loads(canonical_json_bytes(build_source_manifest(ROOT, input_paths=inputs())))


def proof(manifest):
    objects = {}
    def capture(kind, oid):
        raw = subprocess.check_output(["git", "-C", str(ROOT), "cat-file", kind, oid])
        if object_id(kind, raw) != oid:
            raise ValueError("native source object ID")
        objects[oid] = dict(kind=kind, base64=base64.b64encode(raw).decode())
        return raw
    commit, tree = (manifest["git"][k] for k in ("commit_sha", "tree_sha"))
    if capture("commit", commit).split(b"\n", 1)[0] != ("tree "+tree).encode():
        raise ValueError("source commit/tree")
    entries = walk_tree(tree, capture)
    for path in selected(entries):
        capture("blob", entries[path][1])
    return objects


def verify_source(manifest, objects):
    check_seal(manifest, "manifest_sha256")
    if manifest["git"]["tracked_dirty"]:
        raise ValueError("dirty execution source")
    def get(kind, oid):
        if oid not in objects or objects[oid]["kind"] != kind:
            raise ValueError("missing/wrong source proof object")
        raw = base64.b64decode(objects[oid]["base64"], validate=True)
        if object_id(kind, raw) != oid:
            raise ValueError("source proof object hash")
        return raw
    commit, tree = (manifest["git"][k] for k in ("commit_sha", "tree_sha"))
    if get("commit", commit).split(b"\n", 1)[0] != ("tree "+tree).encode():
        raise ValueError("source commit/tree")
    entries = walk_tree(tree, get)
    rows = manifest["inputs"]
    paths = [safe_relative(r["path"]) for r in rows]
    if len(paths) != len(set(paths)) or set(paths) != selected(entries):
        raise ValueError("complete source inventory")
    for row in rows:
        mode, oid = entries[row["path"]]
        if mode not in ("100644", "100755") or hashlib.sha256(get("blob", oid)).hexdigest() != row["sha256"]:
            raise ValueError("source input hash/type")
    for path, digest in FROZEN.items():
        if next(r["sha256"] for r in rows if r["path"] == path) != digest:
            raise ValueError("anchored preregistration changed")
    return True


def save_archive(path, payload):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(gzip.compress(canonical_json_bytes(payload), mtime=0))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(path)
        _replace_with_retry(temporary, path)
    finally:
        _cleanup(temporary)


def load_archive(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def verify_gate(gate, expected_source):
    """Same complete, solver-free gate proof for live startup and offline replay."""
    from robust_budget_allocation.pilot.replay import verify_environment
    check_seal(gate)
    if gate["status"] != "PASS" or gate["frozen_hashes"] != FROZEN or not same(gate["source"], expected_source):
        raise ValueError("prelaunch source/registration gate")
    verify_source(gate["source"], gate["git_objects"])
    verify_environment(gate["environment"])
    names = {"solver-free", "licensed"}
    if set(gate["suites"]) != names or set(gate["xml_files"]) != names:
        raise ValueError("missing gate suites/XML")
    for name, row in gate["suites"].items():
        raw = gate["xml_files"][name].encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != row["xml_sha256"]:
            raise ValueError("gate XML hash")
        xml = ET.fromstring(raw)
        if any(sum(int(s.attrib.get(k, 0)) for s in xml.iter("testsuite")) != row[k]
               for k in ("tests", "failures", "errors", "skipped")):
            raise ValueError("gate XML counts")
        if row["returncode"] or row["errors"] or row["failures"] or row["tests"] <= row["skipped"]:
            raise ValueError("failed/empty gate suite")
        if name == "licensed" and row["skipped"]:
            raise ValueError("skipped licensed gate")
    return True
