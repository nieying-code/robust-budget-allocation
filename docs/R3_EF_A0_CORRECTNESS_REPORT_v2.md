# R3 EF + Standard C&CG Correctness Report

Status: **R3 delivery — ready for independent review after Draft PR creation**

Scope: finite-scenario EF benchmark, A0 Standard exact C&CG, frozen numerical protocol, correctness certificates, replay and integrity tests for the reviewed heterogeneous-material Q-F-R v2 model family. No A1, pilot, OOS scientific evaluation, formal experiment or performance claim is included.

## 1. Governance and source anchors

R3 started from the clean merged R2 `main` commit `d5484adff21040bdaa0aaa3e727c9d341b342e47`, tree `30d3e0ed261b794de8420bd9bd1c0d9873ee4e29`, on branch `r3/ef-a0-correctness`.

The user explicitly re-registered the authorized generic N4 numerical and deterministic rules as the new R3 v2 protocol. The protocol was committed before any R3 licensed comparison:

- protocol freeze commit: `c29a67c1369f44c4afb424c0ba2a8b0d43a0b923`;
- protocol freeze tree: `ba4c8d3855b6f027509a5bbd85af88d7bb48f9b5`;
- protocol SHA-256: `cd0e02603cd307876b3270e2c694127541394211d7034325dabdee2f28b7bf0b`.

This provenance does not inherit the old Q-R-F model, F-OPTION, old Reliability semantics, data, fixtures, scenarios, parameters, results or conclusions. Old N4/N5/N6 code and evidence remain historical and unchanged.

The first executable implementation anchor was commit `819f673b25db17245b9e11ec7e34de3d62f2bf81`, tree `14764cd84d64ae60694806d4d67783e6f293e3ca`. Historical replay hardening and negative tests were committed at `ee35252620c8c680695fcbe77e2fd461d0a20da9`, tree `e9ba89f758b89117d3753a86490479b3a1f5c269`. Shallow-checkout replay portability was repaired at commit `70704725a1f8c594e5125d83f3d7481e9e19cde4`, tree `c8e981f296a2305948e6191145ce59497f076df6`. Independent-review B1 fail-closed validation was implemented at `0c49cb0ac211eca1a27bf37826a855b78fce5229`; tuple/list normalization for the existing `validate_source_state` contract was completed at clean execution commit `d83475e6dc9afdb69f30c8214cdddefe081af1e1`, tree `d49bd70011b314e2b422b5d2a6073a8f0efe5c59`. The final correctness rerun is bound to that clean source. Final delivery commit/tree and Draft PR are external anchors to avoid self-referential hashes.

R1 classification totals remain unchanged: 39 `DIRECT_REUSE`, 29 `REUSE_WITH_MODIFICATION`, 85 `HISTORICAL_ONLY`, and 4 `REWRITE_REQUIRED`.

## 2. Frozen R3 v2 protocol

The protocol defines `T(a,b)=1e-7+1e-9*max(1,abs(a),abs(b))`, exact accepted status, full finite-scenario oracle requirements, canonical initial scenario, exact-value tie handling, complete scientific scenario identity, duplicate rejection, formal LB/UB ownership, convergence/violation checks and `len(Omega)+1` iteration safety.

Licensed EF, master and recourse solves use `gurobi_direct`, Threads=1, no fallback, MIPGap=0, MIPGapAbs=0, FeasibilityTol=1e-9, OptimalityTol=1e-9 and IntFeasTol=1e-9. Only `SolverStatus.ok` paired with `optimal` or `globallyOptimal` is accepted.

The protocol, source, data, fixture, scenario realization, solver, ordered active pools, all master bounds, every full oracle result, first-stage decision, certificate and replay are hash-bound and validated fail-closed.

## 3. EF implementation

The R3 EF adapter invokes the reviewed R2 M0/M1/M2 builder on the complete finite scenario set. It introduces no second scientific formulation. Q/F/z remain shared first-stage decisions; x/u remain scenario-indexed recourse. Fixed-budget, shortage, heterogeneous retention/storage and F-specific reliability equations are exactly the R2 implementation.

After each accepted EF solve, R3 performs R2 loaded-solution validation and independently solves exact recourse for every scenario at the returned first-stage decision. EF is accepted only when its objective equals first-stage cost plus independently optimized worst recourse within the frozen tolerance and all identities/accounting validate.

## 4. A0 Standard C&CG

A0 starts with the smallest canonical scenario ID. Every restricted master is the reviewed R2 builder applied to the current scientific scenario pool. The restricted-master exact optimum owns the formal LB.

Every successful master iteration invokes one complete exact oracle over all original scenarios in canonical order. Each fixed-decision scenario recourse is a linear model with the reviewed demand, fulfillment and fixed-total-budget accounting. Only `C_pre + max_omega recourse_omega` from a complete successful oracle may update formal UB. The exact worst scientific scenario is added only when it violates the current master threshold and is not already represented. Duplicate identity, bound crossing, incomplete oracle, no-progress gap and iteration exhaustion fail closed.

The active A0 v2 path imports no memory, candidate ranking, shortlist, heuristic screening, learned state, old phase logic or A1 module.

## 5. Preregistered correctness fixture

`tests/fixtures/r3_correctness_v2.json` is marked `CORRECTNESS_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS`. Its SHA-256 is `322a43f29019beee9dcb91fa003b2c842260f38b8d15735119abc730808eb11d`.

The fixture has three heterogeneous items and three finite scenarios, including zero disruption and positive item-specific disruption. It exercises M0, M1 and M2, fixed shared budget accounting, positive shortage, positive flexible exercise in the full M2 result and nontrivial generation from initial `a_zero_disruption` to added `c_peak`. These values are development correctness inputs only; no formal calibration is frozen and no mechanism-activation conclusion is drawn.

## 6. Licensed EF approximately equals A0 evidence

All comparisons below passed the preregistered protocol.

| Model | EF objective | A0 objective | Absolute difference | A0 iterations | Final pool |
| --- | ---: | ---: | ---: | ---: | --- |
| M0 = Q | 535.9097744360902 | 535.9097744360902 | 0 | 2 | `a_zero_disruption`, `c_peak` |
| M1 = Q+F | 535.9097744360902 | 535.9097744360903 | 1.1368683772161603e-13 | 2 | `a_zero_disruption`, `c_peak` |
| M2 = Q+F+R | 510.3732625331875 | 510.3732625331876 | 5.684341886080802e-14 | 2 | `a_zero_disruption`, `c_peak` |

Aggregate certificate summary:

- accepted comparisons: 3/3;
- maximum objective difference: `1.1368683772161603e-13`;
- maximum independently recomputed recourse feasibility violation: `0`;
- maximum recorded final gap/violation magnitude: `1.1368683772161603e-13`, within frozen thresholds;
- A0 iterations: 6 total;
- complete exact oracle calls: 6;
- finite-scenario evaluations: 18;
- every A0 iteration executed one full oracle before convergence decision.

This is a numerical correctness result on a small deterministic fixture, not a scientific comparison or performance result.

## 7. First-run and replay provenance

The first command was rejected before environment preflight or any solve because the source gate detected untracked generated `egg-info` packaging metadata. Those untracked generated files were removed; this event was not a licensed EF/A0 comparison.

The first actual licensed comparison on execution commit `819f673...` passed all three models. Its immutable evidence is `docs/evidence/R3_CORRECTNESS_FIRST_RUN_v2.json`, sealed evidence SHA-256 `fa366744d314201194002bdcd5c89c5abbe4da597af0a533bffff50e13a27d87`.

While constructing adversarial tests, self-review found that replay should compare embedded fixture payloads directly with their execution-commit content and should resolve source hashes from the recorded commit rather than the mutable working tree. This ordinary R3 replay defect did not alter equations, protocol, fixture or numerical results. The original evidence was preserved. After the fail-closed historical replay repair, every affected case was rerun from clean commit `ee352526...`.

The first Draft-PR CI run then exposed a portability defect: GitHub Actions uses a shallow checkout in which the earlier execution commit is not initially present. Replay correctly failed rather than weakening verification. The validator now fetches only the exact recorded commit from the configured `origin` when that object is missing, then performs the same commit-to-tree-to-blob/hash validation. Fetch or identity failure remains fail-closed. No model, algorithm, protocol, fixture or numerical result changed; all correctness cases were rerun again from the repaired clean source.

Independent review then demonstrated that schema-v1 replay trusted resealed environment, source inventory, summary, EF/master accounting and master-bound fields. The original first-run artifact remains immutable with its original seal; it is retained as provenance, not treated as the final fail-closed certificate. The repaired schema-v2 validator now consumes the existing `validate_source_state` output, binds the reviewed R2 model source, validates the locked licensed environment and solver policy, independently closes EF/master accounting and the solver-objective/bound to master/LB/trace chain, and recomputes the complete summary.

The first post-review licensed execution completed all solves but was rejected before evidence write because the new validator incorrectly required JSON lists from the in-process `validate_source_state` result, which correctly returns tuples. This engineering gate failure was retained in the task provenance; it was not a scientific or numerical failure. After normalizing the existing return representation without adding a second source-state framework, the three preregistered cases were rerun from clean commit `d83475e...`.

Final evidence is `docs/evidence/R3_CORRECTNESS_RESULTS_v2.json`, sealed evidence SHA-256 `c1ab922d13641ea69df061bf2fe8467a40cd49e9f753f76eb87b36141f174621`. Final schema-v2 replay PASSes from its recorded execution commit/tree. The original schema-v1 first-run seal and execution anchor remain preserved unchanged.

## 8. Integrity and regression tests

Negative tests reseal tampered objects and confirm rejection of:

- source hash and protocol identity changes;
- full data and scenario hash changes;
- demand or disruption changes under identical indices;
- static item-parameter changes;
- objective tampering;
- LB history and scenario-addition tampering;
- missing exact-oracle evidence;
- false convergence;
- wrong solver status;
- missing mandatory audit fields;
- altered locked environment/Threads and frozen solver configuration;
- empty source inventory and tracked-input inventory;
- falsified accepted count, failures and iteration summary;
- altered EF and restricted-master accounting objective/theta;
- detached master solver objective/lower bound.

Final test results:

- focused R3 solver-free structure/replay/attack/delivery tests: `30 passed`;
- full solver-free regression: `831 passed, 102 deselected`;
- full licensed regression: `102 passed, 831 deselected`;
- preregistered R3 licensed correctness suite: `3 passed comparisons`;
- original first-run evidence: immutable schema-v1 seal verified and preserved;
- final rerun replay: PASS.

Environment: CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, Threads=1, solver/license available, no fallback.

## 9. Scope and classification audit

- No R2 scientific/model file changed.
- No existing `DIRECT_REUSE` production file changed; generic hashing, Git-state, atomic I/O, environment and solver-status infrastructure are imported unchanged.
- Old algorithm/evidence paths remain unchanged and historical.
- New `qfr_*` algorithm modules implement the R1 `REUSE_WITH_MODIFICATION` requirements without weakening old replay.
- Complete scenario identity contains static QFR identity plus item-indexed demand and disruption, not scenario index alone.
- EF uses full finite Omega; A0 uses restricted masters and full exact Oracle on every iteration.
- LB comes from the restricted-master exact optimum; only full exact oracle results update UB.
- Scientific symbol audit found no `y_F`, `K_F`, F-OPTION, Q-protecting Reliability, supplier dimension, dynamic perishability, DRO or emergency fund in the active v2 R3 path.
- A0 has no A1/memory/candidate dependency.

## 10. Limitations and deferred work

- Evidence covers a small deterministic multi-item correctness fixture only. It provides no performance, scalability, calibration or policy claim.
- Runtime and iteration counts are audit metadata only.
- No independent OOS scientific evaluation was executed.
- A1_new remains completely unimplemented and unfrozen for R4.
- Pilot/mechanism diagnosis remains R5; formal numerical design remains R6; formal experiments/results remain R7–R8.

Scientific runs = 0. Pilot runs = 0. Formal experiments = 0. A1_new implemented = NO.
