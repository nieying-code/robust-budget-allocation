"""Git-object authenticated historical source proofs, including shallow CI."""

import base64
import gzip
import hashlib
import json
from functools import lru_cache
import subprocess

from .configuration import ROOT
from .storage import safe_relative, check_seal

ARCHIVE_PATH = "docs/evidence/N6_SOURCE_OBJECTS.json.gz"
PILOT02_PROOF_PATH = "docs/evidence/N6_PILOT02_PRELAUNCH.json.gz"
AUTHORIZATION = "docs/N6_HARNESS_REPAIR_AUTHORIZATION.md"
FIXED = {"scripts/n6_pilot.py", "docs/N6_PILOT_PROTOCOL.md", "configs/pilot/n6_candidates.json",
         "docs/N4_CORRECTNESS_PROTOCOL.md", "docs/N5_A1_PROTOCOL.md", "pyproject.toml", "requirements.txt"}


def object_id(kind, raw):
    return hashlib.sha1(kind.encode()+b" "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def tree_entries(raw):
    offset = 0
    while offset < len(raw):
        end = raw.index(b"\0", offset)
        mode, name = raw[offset:end].split(b" ", 1)
        oid = raw[end+1:end+21]
        if len(oid) != 20:
            raise ValueError("truncated Git tree")
        yield mode.decode(), name.decode("utf-8"), oid.hex()
        offset = end+21


def walk_tree(tree, get, prefix=""):
    entries = {}
    for mode, name, oid in tree_entries(get("tree", tree)):
        path = prefix+name
        safe_relative(path)
        if mode in ("40000", "040000"):
            entries.update(walk_tree(oid, get, path+"/"))
        else:
            entries[path] = (mode, oid)
    return entries


def selected(entries):
    names = {p for p in entries if p.startswith("src/robust_budget_allocation/") and p.endswith(".py")} | FIXED
    if AUTHORIZATION in entries:
        names.add(AUTHORIZATION)
    if "docs/N6_FRESH_RESTART_AUTHORIZATION.md" in entries:
        names.add("docs/N6_FRESH_RESTART_AUTHORIZATION.md")
    return names


@lru_cache(maxsize=1)
def archive_objects():
    archive = json.loads(gzip.decompress((ROOT / ARCHIVE_PATH).read_bytes()))
    if archive["schema_version"] != 1:
        raise ValueError("source archive schema")
    objects = dict(archive["objects"])
    proof_path = ROOT / PILOT02_PROOF_PATH
    if proof_path.exists():
        if proof_path.is_symlink() or not proof_path.is_file():
            raise ValueError("nonregular pilot02 source proof")
        proof = json.loads(gzip.decompress(proof_path.read_bytes()))
        check_seal(proof, "evidence_sha256")
        source = proof["source"]
        check_seal(source, "manifest_sha256")
        extra = proof["git_objects"]
        if proof["schema_version"] != 1 or extra["schema_version"] != 1:
            raise ValueError("pilot02 source proof schema")
        if extra["commits"] != [source["git"]["commit_sha"]] or source["git"]["tracked_dirty"]:
            raise ValueError("pilot02 source proof anchor")
        for oid, item in extra["objects"].items():
            decode_object(item["kind"], oid, item)
            if oid in objects and objects[oid] != item:
                raise ValueError("conflicting Git source proof object")
            objects[oid] = item

        def from_archive(kind, oid):
            if oid not in objects:
                raise ValueError("missing Git source proof object: " + oid)
            return decode_object(kind, oid, objects[oid])

        # Authenticate the proof's own source inventory too, without consulting
        # live files, fetching history, importing archived code or recursing here.
        expected = _authenticate_inputs(source["git"]["commit_sha"],
                                        source["git"]["tree_sha"], from_archive)
        entries = source["inputs"]
        paths = [safe_relative(e["path"]) for e in entries]
        if len(paths) != len(set(paths)) or set(paths) != set(expected):
            raise ValueError("pilot02 source proof inventory")
        if any(e["sha256"] != expected[e["path"]] for e in entries):
            raise ValueError("pilot02 source proof input hash")
    return objects


def decode_object(kind, oid, item):
    if kind not in ("blob", "tree", "commit") or item["kind"] != kind:
        raise ValueError("Git source proof type")
    raw = base64.b64decode(item["base64"], validate=True)
    if object_id(kind, raw) != oid:
        raise ValueError("Git source proof object hash")
    return raw


def get_object(kind, oid):
    if len(oid) != 40 or any(c not in "0123456789abcdef" for c in oid):
        raise ValueError("invalid Git object ID")
    result = subprocess.run(["git", "-C", str(ROOT), "cat-file", kind, oid], capture_output=True)
    if result.returncode == 0:
        raw = result.stdout
    else:
        objects = archive_objects()
        if oid not in objects:
            raise ValueError("missing Git source proof object: " + oid)
        raw = decode_object(kind, oid, objects[oid])
    if object_id(kind, raw) != oid:
        raise ValueError("Git source proof object hash")
    return raw


def authenticate_inputs(commit, expected_tree):
    return _authenticate_inputs(commit, expected_tree, get_object)


def _authenticate_inputs(commit, expected_tree, get):
    raw = get("commit", commit)
    tree_line = raw.split(b"\n", 1)[0].decode()
    if tree_line != "tree "+expected_tree:
        raise ValueError("source commit/tree mismatch")
    entries = walk_tree(expected_tree, get)
    hashes = {}
    for path in selected(entries):
        mode, oid = entries[path]
        if mode not in ("100644", "100755"):
            raise ValueError("nonregular anchored source")
        hashes[path] = hashlib.sha256(get("blob", oid)).hexdigest()
    return hashes


def build_archive(commits):
    """Read Git only; caller atomically saves compact proof, never executes this source."""
    objects = {}
    def capture(kind, oid):
        raw = subprocess.check_output(["git", "-C", str(ROOT), "cat-file", kind, oid])
        if object_id(kind, raw) != oid:
            raise ValueError("Git object mismatch")
        objects[oid] = dict(kind=kind, base64=base64.b64encode(raw).decode())
        return raw
    for commit in commits:
        raw = capture("commit", commit)
        tree = raw.split(b"\n", 1)[0].decode().removeprefix("tree ")
        entries = walk_tree(tree, capture)
        for path in selected(entries):
            mode, oid = entries[path]
            if mode not in ("100644", "100755"):
                raise ValueError("nonregular source")
            capture("blob", oid)
    return dict(schema_version=1, commits=list(commits), objects=objects,
                purpose="read-only authenticated source provenance; not a runnable source migration")
