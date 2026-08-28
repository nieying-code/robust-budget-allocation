# Transition engineering hardening (not a scientific stage)

Base: 17994d9467cb265e032b5aee1b5dc843b9ae3f7c; tree:
905d7b6d733f1a38a491bfa8662720de98058911.

This change follows the PR #9 transition delta audit. PR #9 itself is not
merged or cherry-picked. Only separable engineering increments are reimplemented
from the N6 main base. No diagnostic package, configuration, protocol, seeds,
scientific summary or evidence is imported. Scientific runs = 0. No R0 or
other scientific phase is started; no automatic merge is authorized.

## Implementation

- B1: reproducibility/test_evidence.py validates original JUnit SHA256, declared
  suite counts, return code and nonempty passed execution. pilot/restart.py uses
  it in live validation and production replay. All four existing N6 gate suites
  remain mandatory with the same no-skip policy. Historical XML is read from the
  already delivered prelaunch archive, with its seal and complete gate/source
  binding checked. No historical bytes are rewritten. Future bundles include
  gate_xml_files; absent/mismatched evidence fails closed.
- B2: pilot/replay.py additionally binds the entire inner engine source to the
  outer manifest using the existing canonical_json_bytes serialization. Existing
  source seals, native Git proof and data/config checks remain in force.
- B3: scripts/n6_pilot.py archive() calls the existing bounded replace helper.
  Deterministic gzip, flush/fsync, temporary file, no-overwrite checks and caller
  lease semantics are unchanged. This is preventive integration, not a claim of
  an observed archive failure. Retry remains 20 attempts at 0.05 seconds.
- B4: new tests exercise the actual production source entry in real depth-one
  clones, without mocking its validators. They cover sibling packaging metadata,
  ignored/untracked protected inputs, required files, tracked tampering and
  persisted source JSON. The correct package scanning boundary already exists
  on main and is NOT changed. N1 validator and solver policy are NOT changed.

## Evidence and hash continuity

N0-N6 scientific artifacts and frozen hash lists remain byte-identical. The N6
hash test now distinguishes four explicitly superseded engineering/test files
from the frozen files: original digests remain bound to the unchanged N6 list,
and current digests are recorded in TRANSITION_ENGINEERING_MANIFEST.json. Its
exact allowlist is independently tested. No wildcard exemption or skipped hash
check is introduced. The manifest excludes itself; Git commit/tree is its
external anchor. All other N6 hash entries must still match current bytes.

## Validation

Validation results are reported with the final commit and PR checks. Tests use
synthetic engineering data or read-only historical evidence, never new scientific
solves. No licensed suite, pilot, diagnostic study or formal experiment is run
for this patch. Existing solver-free regression includes historical replay and
Windows engineering stress tests where applicable.
