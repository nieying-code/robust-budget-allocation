# N6 read-only replay delivery repair

Authorization: N6_READONLY_REPLAY_FIX_AUTHORIZED; N7_NOT_AUTHORIZED.
Continue the existing Draft PR #8. No pilot, licensed suite, prelaunch, parameter
change, merge or N7 work is authorized or performed in this repair.

## Confirmed defect and boundary

The 80 accepted n6pilot02 runs and their mathematical/accounting replay passed
external review. The delivered CLI failed in a genuine depth=1 checkout because
the execution commit was absent from local Git and the production source-object
fallback loaded only N6_SOURCE_OBJECTS.json.gz. The new proof was already shipped
inside N6_PILOT02_PRELAUNCH.json.gz, but only a monkeypatched test fixture supplied
its objects. That fixture hid a production delivery gap; CI success was not proof
of real shallow-clone replay. This is reproducibility, not a solver/model failure.

Immutable execution commit ec6bbfc55e333483efa41f866c0e8f26d13cd18f and tree
1856c203917fa3cc234f5aee83e2a4403abe472d remain the sole scientific anchor.
The scientific evidence, prelaunch proof, summary, run manifest and all old
failure/diagnostic archives are unchanged. No historical Git rewrite or fetch
is needed. PR #7's premature merge remains a governance event, not scientific
approval, readiness or permission to enter N7.

## Read-only repair

Only pilot/source_archive.py changes production behavior. It loads the existing
pilot02 proof alongside the historical store when native Git objects are absent.
It validates the proof and source seals, schemas, declared anchor, every extra
object's type/base64/native Git object ID, duplicate-object consistency, exact
commit/tree binding and full source inventory/hashes. Normal record-source
authentication remains unchanged. Missing required objects fail with ValueError,
not an opaque KeyError or a success fallback. No archived source is imported or
executed; no history is fetched and no scientific solver is invoked.

The old autouse fixture that monkeypatched the new object store into evidence
tests is removed. Existing production CLI dispatch and frozen model/algorithm
definitions are unchanged.

## Genuine shallow CLI regression

tests/test_n6_shallow_cli_replay.py invokes Git clone --depth=1 --no-local through
file transport into a new temporary directory for each case. It checks shallow
status, exactly one reachable commit and absence of the historical execution
commit both before and after the actual CLI subprocess. The cloned production
files must equal the committed delivery; no working-file overlay is allowed.
No monkeypatch, validator substitution, source-store injection, history fetch
or solve simulation is used. GRB_LICENSE_FILE names a nonexistent file; readonly
replay must succeed without a license. No outputs directory may be created.
Clone-local core.autocrlf=false preserves committed bytes for the frozen file
hashes; no global Git setting is changed and no files are overlaid or rewritten.

Command inside the depth=1 clone:

    python scripts/n6_pilot.py replay --evidence docs/evidence/N6_PILOT02_EVIDENCE.json.gz

Expected positive result: PASS, 80 runs, 80 successes, 0 failures, 16 pairs,
max_pair_difference=0. Six isolated negative clones remove the proof file or
commit object, corrupt native object bytes, break the proof seal, or forge tree
or input inventory. Except for the deliberately broken-seal case, outer seals
are recalculated, so stored digest presence alone cannot pass. Every negative
CLI must exit nonzero without printing PASS. Original evidence is never touched.

## Validation status

First validation at repair commit a98984552f7b5ba89b96b9166edf7cadff8dfc9a:
13 existing artifact tests passed; 7 shallow tests stopped in setup before CLI
because the host's automatic CRLF checkout differed from committed LF bytes.
This test-setup failure is retained in
outputs/harness-validation/n6-readonly-replay-fix-v1/targeted.xml. The fixture now
explicitly disables clone-local newline conversion; production loading is unchanged.

Validated clean repair/test commit: 1a4bb52a5ba05c7b88c60800a07094e0cc4e6293.
Tree: ac0df24a16f63600c6c72c37983714d7776a24f4. The production audit repair was
committed in a98984552f7b5ba89b96b9166edf7cadff8dfc9a; the next commit changed
only clone setup, documentation and delivery hashes. No scientific execution
anchor changes; final report/hash commits are external delivery anchors only.

Actual validation on the committed repair:

- Targeted: 20 passed (7 real shallow CLI cases plus 13 existing evidence cases).
- Full solver-free: 622 passed, 100 licensed deselected, 3 existing JUnit warnings.
- Independent retained clone: outputs/harness-validation/n6-readonly-replay-fix-v2/standalone-depth1.
  Shallow=true, reachable commits=1, Git cat-file cannot find the execution commit;
  the normal CLI nevertheless returns PASS, 80 successes, 0 failures, 16 pairs,
  max_pair_difference=0. Its working tree remains clean; no outputs were created.
- Every negative clone fails without PASS, including resealed object/tree/inventory
  forgeries. No monkeypatch, source-store injection or fetch in these CLI tests.
- Current 45-entry N6 delivery hash inventory excludes itself. Original pilot,
  prelaunch, manifest, summary and historical evidence files have no Git diff.

Raw JUnit is retained separately as targeted.xml and solver-free.xml under
outputs/harness-validation/n6-readonly-replay-fix-v2. The first failed setup log
is not overwritten. Final delivery-head CI remains attached to the same Draft
PR #8, separate from these local test records. Hosted licensed jobs remain gated.
No pilot, licensed suite, prelaunch, parameter tuning, merge or N7 work occurred.

The delivery gap is repaired and submitted for external review. No change to the
scientific diagnosis: Q/R and Candidate response are observed; Option and Memory
benefit remain unproven, and their linked coverage limitation is still explicit.
N6_READY_FOR_PR_REVIEW is not final scientific approval or N7 authorization.
