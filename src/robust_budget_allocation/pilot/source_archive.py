"""Git-object authenticated historical source proofs, including shallow CI."""

import base64
import gzip
import hashlib
import json
from functools import lru_cache
import subprocess

from .configuration import ROOT
from .storage import safe_relative

ARCHIVE_PATH = "docs/evidence/N6_SOURCE_OBJECTS.json.gz"
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
    return names


@lru_cache(maxsize=1)
def archive_objects():
    archive = json.loads(gzip.decompress((ROOT / ARCHIVE_PATH).read_bytes()))
    if archive["schema_version"] != 1:
        raise ValueError("source archive schema")
    return archive["objects"]


def get_object(kind, oid):
    if len(oid) != 40 or any(c not in "0123456789abcdef" for c in oid):
        raise ValueError("invalid Git object ID")
    result = subprocess.run(["git", "-C", str(ROOT), "cat-file", kind, oid], capture_output=True)
    if result.returncode == 0:
        raw = result.stdout
    else:
        item = archive_objects()[oid]
        if item["kind"] != kind:
            raise ValueError("Git source proof type")
        raw = base64.b64decode(item["base64"], validate=True)
    if object_id(kind, raw) != oid:
        raise ValueError("Git source proof object hash")
    return raw


def authenticate_inputs(commit, expected_tree):
    raw = get_object("commit", commit)
    tree_line = raw.split(b"\n", 1)[0].decode()
    if tree_line != "tree "+expected_tree:
        raise ValueError("source commit/tree mismatch")
    entries = walk_tree(expected_tree, get_object)
    hashes = {}
    for path in selected(entries):
        mode, oid = entries[path]
        if mode not in ("100644", "100755"):
            raise ValueError("nonregular anchored source")
        hashes[path] = hashlib.sha256(get_object("blob", oid)).hexdigest()
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

