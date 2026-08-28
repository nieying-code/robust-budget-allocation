# N6 pilot / execution readiness report

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
