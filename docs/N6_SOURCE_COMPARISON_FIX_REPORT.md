# N6 source-comparison repair — tests only, no pilot relaunch

**N6_BLOCKED. N6_SOURCE_COMPARISON_FIX_AUTHORIZED.
N6_PILOT_RELAUNCH_NOT_AUTHORIZED. N7_NOT_AUTHORIZED.**

This is a local execution/audit repair in the existing Draft PR #8. It is not
N6 completion, permission to rerun gates/pilot, or scientific approval. PR #7's
premature merge remains the governance event recorded in
N6_FRESH_RESTART_AUTHORIZATION.md; history is neither rewritten nor rolled back.

## Defect and full comparison boundary

N1 build_source_manifest returns a tuple for git.untracked_paths. JSON persists
that tuple as an array and loads it as a list. The prior restart compared Python
dictionaries across this boundary. The original zero-run failure at commit
14da8abb5b0735bd5e180f1387d9b32f249fbb1d and all old gate/XML files are preserved.
The same defect also affected the first loaded result and final in-memory replay;
fixing only validate_gates would not have repaired the complete execution chain.

restart.same_content compares canonical_json_bytes of the ENTIRE two values,
not only a stored manifest hash or selected fields. It includes nested metadata,
all input paths/hashes, Git anchors, package/Python data and additional fields.
Tuple/list and dictionary insertion order normalize; array order remains
significant and nonfinite JSON values are rejected. Seals, authenticated Git
objects, exact source inventory and XML hashes remain independently checked.
The N1 manifest API and N1 canonical JSON utility are unchanged.

Applied to gate/live source, gate-generation before/after checks, worker/claim,
per-run before/after and loaded-record checks, final live-source check, and
bundle/record/claim/gate comparisons in restart replay. Commit/tree scalar checks
remain exact. No source check is removed or reduced to digest-field equality.

## Integration coverage, not mock validation

The old orchestration tests replaced validate_gates and final replay with success
stubs and used a simplified tuple-free source. Those tests have been replaced.
New fixtures create a REAL temporary Git repository and call the unchanged N1
manifest builder/source-state validator. They use actual atomic JSON writes,
file inventories/hashes and read_run; gates, worker validation, replay_run,
replay_group, replay_bundle and replay_restart source checks are not mocked.

Only the scientific solve and mathematical optimality predicates are simulated.
Synthetic environments/gate XML/results are labelled fixtures, stay under pytest
temporary directories, and must never be represented as licensed or pilot runs.
A simulated 80-record sequence tests registered order, first-record reload,
in-memory final replay AND final JSON round-trip replay. It is zero scientific
work, not an 80/80 pilot success or new EF/A0/A1 correctness evidence.

Negative tests cover preserved-digest and re-sealed source changes, input hash,
commit, tree, package version, Python executable and extra fields; source drift
in the first result stops before the next simulated result; a real tracked file
edit is rejected; final bundle/claim/gate source tampering is rejected. Worker
claim comparison, nonfinite values and array order are covered as well.

## Authorization interlock and validation provenance

CLI run, worker, diagnostic-retry and restart-gates actions are disabled with
N6_PILOT_RELAUNCH_NOT_AUTHORIZED. Tests call the internal orchestrator only inside
temporary repositories with a simulated solver. No production worker is spawned.
Any future restart requires external review, renewed authorization and gates
bound to its then-current clean source. Old gates cannot validate this repair.

New validation artifacts use outputs/harness-validation/n6-source-comparison-fix-v1,
not outputs/harness-validation/n6pilot02. They will be sealed separately with
tested commit/tree, source manifest, XML hashes and explicit tests-only scope.
The old N6_RESTART_STOP archive, historical pilot/diagnostic archives, old gates,
N6 protocol/config, N0–N5 scientific files and N1 manifest API remain unchanged.

N6 remains BLOCKED pending targeted external review. No pilot was relaunched;
no N7/formal work, merge, force push or modification of the frozen design occurred.
