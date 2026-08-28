# N6 pilot / execution readiness report — fresh n6pilot02

Current assessment: **N6_READY_FOR_PR_REVIEW**, with explicit narrower Option
and Memory coverage warnings. This is a submission for external review, NOT
scientific approval, permission to merge, N7 entry or formal experiment authority.
PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS.

## Governance and preserved history

N6 PR #7 was merged prematurely before full pilot completion. This merge is a
governance event only and does not constitute N6 scientific approval, readiness,
or authorization to enter N7.

PR #7 merge: ce12e391f503ca877605f860256a1f86e11d59d8,
2026-08-28T02:22:07Z. At merge N6 was BLOCKED and full pilot incomplete.
Its history was not deleted, rewritten, rolled back or force-pushed. Restart
branch n6/pilot-restart is based on that main commit; all current work stays on
Draft PR #8: https://github.com/nieying-code/robust-budget-allocation/pull/8.

The original n6pilot01 (2 accepted, 1 incomplete, 77 unattempted), single
n6diagnostic01-ef-retry (harness-only), zero-run restart/source-comparison failure,
old gates and tests-only source repair are retained in their separate original
archives/directories. None is included in the 80 fresh observations. The historical
report is retained verbatim below; its state/permissions refer to that earlier time.

## Unique clean execution anchor and prelaunch gates

- Execution commit: ec6bbfc55e333483efa41f866c0e8f26d13cd18f.
- Execution tree: 1856c203917fa3cc234f5aee83e2a4403abe472d.
- Source manifest: dd394759d16c266d68f6e44c8affcb6682dd9a14215755c40685135bd5834236.
- Protocol SHA256: ba60833a951ea4ad69ba123ea421329a1387a0cf581645f8bc7040d0c3414b0d.
- Config SHA256: 974c5b9e13d278cff2ead221d1c838aff4db2c3c3b97314b2595ecb00d6db0d2.
- Independent validation directory: outputs/harness-validation/n6pilot02-prelaunch-v2.

Only necessary gates/run/worker entry was restored and committed first.
Diagnostic-retry stays disabled. The execution commit was clean throughout all
gates and all 80 runs; source is checked before every run, at worker startup,
after reading each result and at final replay. No execution code changed after
launch. Later report/test/artifact commits are NOT execution anchors.

| Ordered gate on execution commit | Actual result |
| --- | --- |
| Solver-free | 602 passed, 100 deselected |
| Windows-only | 4 passed, 15 deselected |
| Real Gurobi licensed | 100 passed, 602 deselected |
| Separate Windows heartbeat atomic read/replace stress | 3 passed, 16 deselected |
| Environment/solver preflight | PASS, real license available |
| Frozen protocol/config/full source inventory and hashes | PASS |
| Actual saved gate JSON -> reload -> production validate_gates | PASS |

Selected gate suites have zero failures/errors/skips. Three JUnit record_property
warnings in each applicable stress suite did not affect execution. Environment:
CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct, Threads=1.
No fallback. Actual roundtrip completed at 2026-08-28T03:34:47.749994Z, before
batch creation at 03:35:31.553279Z. Saved arrays and live tuples differ under raw
Python equality but match in complete canonical content. A saved/reloaded
material source mutation with both seals recomputed was rejected by the actual
validator. No validator or JSON I/O was mocked. The gate file SHA256 is
acc47581c5afa594b91e5d74cd93a163a15295fa937c2899f049e60103710905.

All gate outcomes, clean anchor and batch nonexistence were reported before the
one authorized launch. New compact prelaunch proof includes raw gates/roundtrip,
negative fixture, all four XML reports and authenticated native Git source objects.
Old validation materials are not used as validation of this new execution commit.

## Fresh execution and mathematical replay

16 configurations, 80/80 success/certified, 0 failures, 16 A0/A1 pairs (32 runs).
Each configuration contains M0, M1, M2-as-EF, A0 and A1, not six separate methods.
Started n6pilot02-00-m0 and completed n6pilot02-15-a0 in frozen alternating order.
Finished 2026-08-28T03:44:21.826313Z. No retry, skipped run, historical result reuse,
seed replacement, timeout adjustment or additional scientific solve occurred.
All records bind the unique commit/tree/source, protocol/config, scenario/data,
environment, timestamps, objective, bounds, certification, trace and output hashes.

Final disk-loaded replay: PASS, 80 runs, 80 accepted certificates, 16 complete
groups, max abs(Z_A0-Z_A1)=0. EF/A0/A1 agree within frozen N4 tolerance;
M2<=M1<=M0, single-B cash, shortage loss outside cash, demand/resource balance,
unused resources, LB/UB/signed_gap/gap_tolerance and full Phase III certification
all reconstruct. Original N5 forged-trace defenses remain unchanged. Process
cleanup is successful with exit code 0 for all 80 supervised runs. Failure paths
were tested, not manufactured as additional pilot runs.

Compact scientific evidence: docs/evidence/N6_PILOT02_EVIDENCE.json.gz,
914574 bytes, SHA256 862d9ea0c57acc5a8406d8be35fc1347177a377ad6d19cf5c8a90170568c3e4b.
Per-run manifest: docs/evidence/N6_PILOT02_MANIFEST.json.
Gate/source proof: docs/evidence/N6_PILOT02_PRELAUNCH.json.gz.
Machine-readable diagnosis/workload/capacity: docs/evidence/N6_PILOT02_SUMMARY.json.
Raw outputs remain only under outputs/pilot/n6pilot02 (ignored by Git).
Final artifact commit/tree are external anchors; no recursive self-hash.

## Scientific informativeness — limited, not formal inference

Paid Reliability occurs in 12/16 M2 configurations (all 10 high-risk cases and
2/6 low-risk cases). M1 improves on M0 in those 12; Quantity changes substantially
with budget/risk. M2 equals M1 in all 16, with y_F=0, E=g=0 throughout. This is a
**persistent Option coverage/claim limitation**, not evidence that Flexibility is
universally useless. The registered model-wide severe-degeneration criterion is
not triggered because Reliability and Quantity respond; actual cross-stage
exercise trade-offs have NOT been observed. See N6_SCIENTIFIC_DIAGNOSIS.md.

A1 has 0 Phase I hits, 26 Phase II hits and 16 Phase III calls over 42 iterations.
All 16 Phase III calls are complete exact certification and terminate their runs;
Phase III is not called every iteration. There are no eligible Memory inspection
entries in these traces: prior candidate hits become active, and the first full
oracle occurs only at termination. No Memory benefit is demonstrated. Candidate
search and exact certification do distinct work; this is not an overhead-only
A0 pattern. The narrow Memory coverage warning remains mandatory.

No model, algorithm, parameters, seeds, tolerances or protocol were changed in
response to these results. No formal effect inference or paper speedup claim.

## Runtime, workload, output and N8 capacity advice

| Metric | A0 | A1 |
| --- | ---: | ---: |
| Algorithm seconds min / median / max | 0.3961 / 0.5992 / 1.6038 | 0.2482 / 0.2751 / 0.5055 |
| Supervisor seconds median / max | 6.0033 / 7.0472 | 5.7363 / 5.9970 |
| Iterations range / total | 2–4 / 42 | 2–4 / 42 |
| Full exact calls range / total | 2–4 / 42 | 1–1 / 16 |
| Scenario evaluations range / total | 24–96 / 576 | 14–28 / 258 |
| Final active set range | 2–4 | 2–4 |
| Added scenarios total | 26 | 26 |
| Run-file bytes median / max | 117081 / 208867 | 112847 / 175097 |

M0/M1/EF median algorithm seconds: 0.01946/0.02567/0.21772; observed maxima:
0.02686/0.03464/0.43935. Algorithm clocks exclude process startup, preflight and
source/result audit. Preflight executes once in each fresh worker, not once per
master/oracle solve. Master solve, full oracle and partial-evaluation solver
times remain separate in each saved result. Partial solver time omits model
building, which remains in residual algorithm time. Supervisor wall includes
startup/preflight/postprocessing, but excludes between-run batch replay overhead.
Total supervisor time is 448.689 s; batch start-to-last-record time is 530.273 s.
This distinction matters for capacity. Run-file payload total is 6,937,183 bytes,
excluding file manifests and batch-level artifacts. Python peak excludes native
solver memory; maximum process-lifetime RSS is 71,647,232 bytes, not call-only.

| Illustrative measured-size A0/A1 pairs | 100 | 1000 |
| --- | ---: | ---: |
| Algorithm hours median / observed slow | 0.0244 / 0.0586 | 0.2442 / 0.5859 |
| Pair supervisor hours median / observed slow | 0.3250 / 0.3623 | 3.2500 / 3.6234 |
| 2x observed-slow supervisor planning hours | 0.7247 | 7.2468 |
| Raw payload MB median / observed max | 22.99 / 38.40 | 229.93 / 383.96 |
| 2x observed-max raw payload MB | 76.79 | 767.93 |

These are decimal MB and illustrative planning units, NOT an N7 matrix, upper
confidence bounds or large-instance/OOS predictions. Add between-run replay,
batch manifests, prelaunch gates and reporting overhead separately. The measured
81.584 s difference between batch elapsed and supervisor sum covers batch
coordination/audit overhead, not extra solver work; final full-batch replay and
prelaunch gates are outside that start-to-last-record interval. 12/24 scenarios and three
suppliers support only local capacity observations. Current measured workload is
practical; any larger N7 matrix needs explicit overhead/scale allowance. No core
E2–E6 question or formal seed/scale was removed or frozen here.

## Tests, checks and handoff

Execution-head push/PR CI passed (runs 33139057718 / 33139059779). Hosted licensed
job is gated/skipped, distinct from the 100 real local licensed passes above.
Post-run local regression: **615 solver-free passed, 100 deselected**, including
13 new archived-evidence/forgery tests (also separately 13/13 passed). Raw JUnit
is retained independently at outputs/harness-validation/n6pilot02-postrun-v1/solver-free.xml.
This is post-run validation, not a substitute for the 602-test prelaunch suite.
Three existing JUnit record_property warnings; zero failures/errors. No licensed
or scientific solves were repeated during post-run solver-free validation.
The post-run artifact regression tests check the full archived replay, true source
object proof in shallow checkouts, raw prelaunch XML, roundtrip/type drift and
negative source evidence, frozen order and manifest, summary recomputation,
history preservation and forgeries. Final artifact-head test/CI outcomes are
external PR checks and the final handoff, not retrospectively prelaunch evidence.

No detected correctness blocker; no registered severe model/A1 risk. Narrow
Option/Memory risks require external review and constrain any future claims.
Recommend review of N6 completion and these warnings; **do not enter N7 now**.
PR #8 remains Draft, unmerged. No N7/N8 or formal experiment work has started.

---

# Historical n6pilot01 report (retained; not the current state)

**N6_BLOCKED — full pilot remains paused; authorized single EF diagnostic PASS.**

Subsequent external-review authorization permitted only a harness repair and ONE
EF diagnostic. It passed at clean execution commit
01cd346d60c2bb0fcf6731f2c9806e17b47e3d57; see N6_HARNESS_REPAIR_REPORT.md.
The original batch/history below remains unchanged. Do not combine its M0/M1
with the new-source diagnostic EF. No full pilot resume or N7 is authorized.

PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

## Registration and immutable execution anchors

- Merged N0–N5 baseline: 9dc61f3f7d4b329a2bcf65084c56bbfc1cee78bc.
- Independent preregistration commit: db31c2551a697461fdd1dfde4b797959217f6e40.
- Protocol: docs/N6_PILOT_PROTOCOL.md.
- Protocol SHA256: ba60833a951ea4ad69ba123ea421329a1387a0cf581645f8bc7040d0c3414b0d.
- Config: configs/pilot/n6_candidates.json.
- Config SHA256: 974c5b9e13d278cff2ead221d1c838aff4db2c3c3b97314b2595ecb00d6db0d2.
- Actual pilot execution commit: 2ae53f0f608d4457eda1150540f5eb3b618048f3.
- Actual execution tree: fe4ebee47c12a1aea1540e00619ec448c4854176.
- Compact archive: docs/evidence/N6_PILOT_EVIDENCE.json.gz, 26,024 bytes.
- Archive SHA256: ba8b56a1c586365cc802463897b7ba2a4d55c6de378751df636ae47990f3aecd.
- Final documentation/test artifact commit and tree are external Git anchors;
  neither the hash list nor an artifact recursively includes itself.

Protocol and config were committed before implementation execution and all
pilot results. No frozen N0–N5 file was changed. Prior to actual pilot creation,
a source-root mistake was diagnosed and corrected; its zero-run history is
preserved in docs/evidence/N6_PRELAUNCH_DIAGNOSTIC.md. A Windows venv-launcher
process-tree cleanup issue was also fixed during synthetic pre-pilot tests.
Neither pre-pilot repair used scientific results. At the initial blocked review,
NO repair/retry had been performed after the actual pilot failure below.

## Planned versus executed

Exactly 16 preregistered configurations; 80 model/algorithm runs; 16 A0/A1 pairs.
Actual batch n6pilot01 attempted only the first config low-s61001-b45-n12:
B=45, low disruption risk, seed=61001, one resource, three suppliers, 12 scenarios.

| Run ID | Method | Outer terminal status | Raw engine status | Included in pilot success |
| --- | --- | --- | --- | --- |
| n6pilot01-00-m0 | M0 | success/certified | optimal | yes |
| n6pilot01-00-m1 | M1 | success/certified | optimal | yes |
| n6pilot01-00-ef | M2 EF | incomplete | optimal | NO |

Three attempted runs: two accepted, one failed/incomplete. No complete
configuration, no A0/A1 run and no paired comparison. Remaining 77 planned runs
were NOT attempted. No seeds replaced, retries launched within that batch, IDs overwritten or
failed files deleted. Full raw artifacts remain under outputs/pilot/n6pilot01/
(ignored by Git); compact archive contains all seven files per attempted run,
including manifests, input data, stdout/stderr, raw engine proof and terminal
supervisor status. No outputs/formal/ or formal registry was created.

## Engineering blocker and diagnosis

The third worker saved an exact-optimal EF result and a complete-stage heartbeat.
The supervisor recorded:

    PermissionError(13, 'Permission denied')
    watchdog.status = incomplete
    watchdog.exit_code = null
    watchdog.wall_seconds = null
    record.certified = false

The saved EF solver/oracle certificate independently passes solver-free
verify_engine. Nonetheless, a valid solver artifact is not a completed supervised
run. The outer failure remains authoritative and must not be promoted to success.

Read-only source inspection is consistent with a transient Windows permission
failure while the supervisor reads a heartbeat that the worker atomically
replaces. This is a **plausible cause, not a fully established root cause**:
the current failure envelope saved repr(exception), not its traceback/filename.
No nonzero solver status, invalid budget or wrong EF objective was observed.
The new synthetic test exercises a heartbeat PermissionError and verifies fail-closed
cleanup; it is not claimed as a reproduction of the exact live OS race.

External review should authorize a focused N6 harness fix before another pilot:
capture full I/O error context, define a bounded heartbeat-read sharing-violation
policy without extending the original deadline, and test it on Windows including
process-tree cleanup. Existing completed/failed runs must remain immutable.
Any retry must use a new run_id, parent_run_id and retry_reason; no automatic
same-batch replay is authorized. Frozen models/algorithms need no proposed change.

## Limited observations and accounting

Both accepted M0/M1 runs have objective 495.7182976095696, C_Q=45, C_R=0,
q=(27.25304910377755, 0, 13.145889552757367), base Reliability, no Option.
The saved-but-incomplete EF artifact has the same objective, base Reliability
and y_F=0. Do not treat it as an accepted M2 pilot outcome.
All saved certificates reconstruct demand/resource balance, same-B cash and
economic loss; shortage penalties remain outside cash. For the observed state,
unused cash and unused resource are zero. This is one low-risk tight-budget
point and cannot establish activation frequency, structural degeneration,
sensitivity or a trade-off pattern. Scientific diagnosis remains NOT ASSESSABLE,
not "no risk". See N6_SCIENTIFIC_DIAGNOSIS.md.

| Timing (seconds) | M0 accepted | M1 accepted | EF failed run: raw only |
| --- | ---: | ---: | ---: |
| Preflight | 0.179246 | 0.177824 | 0.147633 |
| Instance construction | 0.004017 | 0.003607 | 0.006353 |
| Frozen model/algorithm wall | 0.043650 | 0.073103 | 0.384989 |
| Master solve | 0.036671 | 0.064147 | 0.062371 |
| Full oracle | 0 | 0 | 0.307454 |
| Call envelope | 0.043670 | 0.073124 | 0.778765 |
| Supervisor end-to-end | 2.216161 | 2.249486 | unavailable |

Preflight occurs once per fresh worker before call timing, with N1 cache intact.
The frozen algorithm timing excludes source audit and final hashing; wrapper
envelope includes them. A0/A1 boundaries are identical in code but no paired
timing observation exists. EF's 12 raw recourse evaluations are not A0/A1
workload evidence. A0/A1 iterations, hits, calls, active size, max objective
difference, signed gap and comparative runtime are all NOT AVAILABLE.
Python call peaks: M0 164,431 bytes, M1 238,548; lifetime process peaks:
64,081,920 and 66,326,528 bytes. The former excludes native Gurobi; the latter
includes startup. They are single observations, not bounds or scalability claims.

## Audit, failure handling and tests

Solver-free compact replay: status FAIL (faithful execution outcome), 3 runs,
2 accepted certificates, 1 retained failure, 0 pairs, max pair difference null.
This is successful integrity verification of a failed batch, not a passing pilot.
Run inventories/hashes, source/config/scenario bindings and accepted raw accounting
replay pass. Independent read-only EF proof validation also passes but does not
erase its process failure. N5 forged-trace protections remain unchanged.

The harness reuses N1 locking/atomic JSON and adds safe immutable IDs, separate
startup/algorithm/postprocess watchdogs, complete failure records, manifests,
source/data/scenario hashes, read-only interrupted-run inspection and retry lineage.
Synthetic tests cover concurrent lease contention, killed worker/stale lock,
duplicate IDs, path traversal, hash/size/inventory forgery, missing/nonregular
files, atomic replacement interruption, timeout, crash and PermissionError.
No synthetic failure is counted as a pilot run or solver success.

Before launch: 518 solver-free and 100 licensed tests passed; the source-root
regression brought the solver-free set to 519. Post-stop artifact/negative replay
tests: **531 solver-free passed; 100 real licensed tests passed (631 total)**.
These passing tests do not override the observed pilot execution blocker.
Final hosted check outcomes are recorded on the same Draft PR #7. Hosted licensed CI remains
explicitly gated, not faked or replaced by another solver. Local licensed tests
use Python 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct, Threads=1.

## N8 capacity projection — blocked, not fabricated

No A0/A1 timing pair was observed, so no empirical typical/slow pair runtime,
iteration/oracle range, paired raw-output size, or total N8 projection is
defensible. The registered illustrative 100/1000-pair formulas are implemented
but their numeric projection remains empty. M0/M1 single-run times cannot
substitute for A0/A1 or OOS costs.

A successful bounded diagnostic alone cannot support projection. Only after
separate full-batch authorization and actual same-source paired observations
may the registered median/observed-slow formulas and 2x planning contingency be
applied at measured scenario sizes. No N7 scale/seed/repetition freeze is supported.

## Gate

Execution readiness: BLOCKED. Current stored solver math: no detected failure.
Scientific informativeness: NOT ASSESSABLE (coverage stopped at one partial
configuration); no evidence for or against severe model/A1 degeneration.
Recommend **do not enter N7**. Keep single PR #7 Draft for blocker review.
No N7/N8 work or automatic merge has occurred.
