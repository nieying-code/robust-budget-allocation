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

Repair committed before true clone validation. Actual targeted/full solver-free
results and final PR checks will be recorded after execution; none is prelaunch
revalidation or a new pilot result. No change to the existing scientific diagnosis:
Q/R and Candidate response are observed; Option and Memory benefit remain unproven.
