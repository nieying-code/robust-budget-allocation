# Implementation Impact Map v2

Status: **R1 planning output only**. Nothing in this document authorizes implementation.

## 1. Stage interpretation

This map follows the latest authorized transition sequence: R2 implements new M0/M1/M2, R3 implements EF/A0 and new correctness evidence, R4 decides and implements A1_new, R5 is pilot/readiness, R6 freezes formal design, and R7–R8 cover subsequently authorized formal work. This latest explicit sequence is the operational authority for the map. The merged R0 roadmap has older milestone meanings and is therefore `REUSE_WITH_MODIFICATION`; an authorized roadmap synchronization is a hard governance gate before R2 implementation, not an R1 edit.

## 2. Asset impact map

| Current asset | Current role | v2 target role | Classification | Required action | Scientific risk | Engineering risk | Target stage |
|---|---|---|---|---|---|---|---|
| `data/model_data.py` | Single-resource Q schema | Pattern source only | REUSE_WITH_MODIFICATION | Create item-indexed v2 schema; leave old schema intact | Scalar fields could silently collapse heterogeneity | Duplicate validation logic can diverge | R2 |
| `data/mechanism_data.py` | Old supplier Reliability and Option schema | Pattern source only | REUSE_WITH_MODIFICATION | Reuse immutability helpers, not classes/fields | Old F-OPTION leakage | Hash must cover full v2 realization | R2 |
| `models/m0.py` | Supplier Q baseline | New item Q model | REWRITE_REQUIRED | New v2 builder/result path | Old fulfillment and `h/x` semantics conflict | Preserve historical evidence imports | R2 |
| `models/m1.py` | Q + supplier Reliability | Q + F at r=0 | REWRITE_REQUIRED | New builder sharing v2 core | Same name hides different science | Programmatic nesting must be explicit | R2 |
| `models/m2.py` | Q + Reliability + F-OPTION | Q + F + F-specific R | REWRITE_REQUIRED | New builder; prohibit y_F/K_F/old cap | Highest leakage risk | Do not break old replay | R2 |
| `models/mechanism_support.py` | Old result extraction/accounting | V2 result/accounting pattern | REUSE_WITH_MODIFICATION | New item/scenario results and independent recomputation | Double-counting or shortage-in-budget | New constraints need complete validation | R2 |
| Old N2/N3 fixtures/tests/evidence | Old model correctness | Historical regression only | HISTORICAL_ONLY | Retain unchanged; add separate v2 fixtures/tests | Cannot establish v2 nesting | Hash/source evidence binds files | R2 |
| `pilot/configuration.py` | Old scalar generator and N6 registry | No direct v2 generator | REWRITE_REQUIRED | Later create versioned `(d,delta)` generation/config | Old distributions could be mistaken as calibrated | Stable identities/hashes required | R5 |
| `io/*` | Atomic I/O, hash, lock | Same | DIRECT_REUSE | Reuse without scientific changes | None intrinsic | Respect bounded failure semantics | R2 |
| `runtime/*`, `environment.py` | Locked solver/preflight/status | Same | DIRECT_REUSE | Reuse; call preflight before future licensed solve | False certification if bypassed | Process-local cache semantics | R2 |
| `reproducibility/git_state.py`, `manifests.py` | Source proof and manifests | Same primitives | DIRECT_REUSE | Use package-scoped protected roots plus required files | Wrong source anchor invalidates evidence | Builder must not replace validation | R2 |
| `reproducibility/test_evidence.py` | JUnit evidence verification | Same | DIRECT_REUSE | Reuse PR #10 behavior | None intrinsic | Must retain testcase-level checks | R5 |
| `algorithms/extensive_form.py` | Thin old-M2 EF wrapper | V2 EF benchmark | REUSE_WITH_MODIFICATION | New v2 EF equations/result certificate | Old EF values are invalid v2 evidence | Preserve generic solve/audit envelope | R3 |
| `algorithms/exact_oracle.py` | Scalar old recourse and enumeration | V2 complete exact oracle | REUSE_WITH_MODIFICATION | Keep enumeration/certificate pattern; rewrite recourse and validator | Shared budget makes old closed form invalid | Completeness/tie policy needs authority | R3 |
| `algorithms/common.py` | Old model adapter + generic solve checks | V2 model adapter | REUSE_WITH_MODIFICATION | Version adapter and protocol; keep mechanical checks | Old decision fields may leak | Avoid symbol collision with η | R3 |
| `algorithms/standard_ccg.py` | Standard old-model C&CG | A0 Standard C&CG | REUSE_WITH_MODIFICATION | Preserve control invariants, replace all scientific callbacks/trace authority | Incorrect LB/UB ownership if adapter weakens contract | Version traces without breaking old replay | R3 |
| `algorithms/verification.py` | Old EF/A0 replay | V2 correctness replay | REUSE_WITH_MODIFICATION | New v2 fields/protocol/tie rules | Old equality is not v2 evidence | Fail-closed validation required | R3 |
| `a1_memory.py`, `a1_candidates.py`, `memory_guided_ccg.py` | Old Memory-Guided Three-Phase A1 | No selected v2 role | HISTORICAL_ONLY | Retain; do not import into A1_new by default | Could predetermine unfrozen novelty | Hooks can bias design if copied wholesale | R4 |
| `a1_verification.py` | Old A1 state/trace verifier | Possible trace-pattern reference | REUSE_WITH_MODIFICATION | Reuse defensive replay ideas only after mechanism choice | Would validate wrong phases if reused | New state machine needs new proof | R4 |
| `pilot/storage.py` | Immutable runs/lineage/manifests | Generic run storage | REUSE_WITH_MODIFICATION | Extract/version method-neutral storage contract | None intrinsic | Current `RUN_FILES` and statuses are N6-shaped | R5 |
| `pilot/heartbeat.py` | Supervisor heartbeat | Same | DIRECT_REUSE | Retain; document known timing-test note | None | Timing-sensitive assertion remains non-blocking | R5 |
| `pilot/execution.py`, `restart.py` | N6 methods/batch and generic supervision | V2 pilot harness | REUSE_WITH_MODIFICATION | Reuse supervisor/fail-stop patterns; replace protocols/methods/config | Old science could be invoked accidentally | Source anchor and immutable lineage must remain strict | R5 |
| `pilot/replay.py` | N6 scientific and integrity replay | V2 replay | REUSE_WITH_MODIFICATION | Retain PR #10 integrity checks; replace old method/data verification | Resealed wrong science must still fail | Mandatory fields must be method-versioned | R3 |
| `pilot/source_archive.py` | Authenticated Git object archive | Same primitive with new inventory | REUSE_WITH_MODIFICATION | Reuse object validation; issue new selectors/proofs | Wrong inventory can omit science | No dependence on full history | R5 |
| `pilot/measurement.py`, `summary.py` | Old model/algorithm metrics | V2 diagnostics | REUSE_WITH_MODIFICATION | Replace y_F/supplier/Option metrics; preserve timing aggregation | Old interpretation would mislabel Q-F-R | Projection assumptions must be explicit | R5 |
| `pilot/diagnostic.py` | One-off N6 repair authorization | Historical path | HISTORICAL_ONLY | Do not activate for v2 | Unauthorized retry | Fixed IDs/reason/source proof | R5 |
| `scripts/n2_*` through `n6_pilot.py` | Historical correctness/pilot CLIs | Pattern reference only | HISTORICAL_ONLY | Leave untouched; create new authorized scripts later | Old route accidental execution | Historical hashes depend on them | R2 |
| `statistics/*` | Pure inference/risk helpers | Future v2 analysis helpers | DIRECT_REUSE | Reuse computations; freeze formal settings later | Defaults are not scientific decisions | Bootstrap memory at large resample counts | R6 |
| OOS evaluator | Not implemented | Independent v2 OOS evaluator | REWRITE_REQUIRED | Create only after formal interface/design authorization | Train/test leakage | Source/config/run binding needed | R6 |
| `.github/workflows/ci.yml` | Solver-free + licensed skeleton | Same | DIRECT_REUSE | Extend tests as stages arrive | CI success cannot substitute licensed evidence | Licensed runner remains conditional | R2 |
| `configs/solver.yaml`, requirements | Locked environment | Same | DIRECT_REUSE | Keep no fallback/Threads=1 | Solver drift | Version mismatch must fail fast | R2 |
| `configs/pilot/n6_candidates.json` | Old pilot values | None | HISTORICAL_ONLY | Never promote to v2 formal parameters | Results-driven inheritance | Accidental config discovery | R5 |
| v1 documents, N2–N6 reports/evidence | Old-route record | Historical provenance | HISTORICAL_ONLY | Keep immutable and outside v2 active path | Misrepresenting old evidence as new | Existing replay still depends on files | R2 |
| R0 v2 scientific design documents, excluding the roadmap | Current scientific authority | Same | DIRECT_REUSE | Read-only scientific baseline | Unauthorized reinterpretation | Hash/source authority must be recorded | R2 |
| `docs/PROJECT_ROADMAP_v2.md` | R0 milestone plan | Current authorized R1 audit/R2–R6 sequence | REUSE_WITH_MODIFICATION | Synchronize through an authorized governance change before R2 starts | Conflicting stage authority could start the wrong work | Preserve R0 provenance while establishing a single active roadmap | R2 |
| Root README/STATUS/package docstrings | Old active-route description | V2 navigation | REUSE_WITH_MODIFICATION | Update later with explicit hash/provenance plan | Readers may follow old science | Historical manifests bind some content | R2 |
| Final A1_new mechanism | Not present/frozen | Improved C&CG | UNCLEAR / NEEDS_DECISION | Dedicated R4 design decision and fresh validation | Premature novelty claim | New verifier/evidence required | R4 |
| Formal configs/seeds/scales/OOS counts | Not frozen | Formal experiment authority | UNCLEAR / NEEDS_DECISION | Freeze only after pilot | Tuning after results | Capacity/runtime limits | R6 |

## 3. R2 minimum implementation boundary

R2 implementation is blocked until the active roadmap is synchronized with the latest authorized sequence. The following boundary applies after that governance gate is closed.

### R2 should create

Names are recommendations, not frozen APIs:

- `data/qfr_data.py`: a new immutable item/scenario schema, independent of old `BudgetAllocationData`, containing v2 static parameters and complete `(d_iω, δ_iω)` realizations.
- `models/qfr_common.py`: shared v2 sets, costs, first-stage variables, and accounting expressions.
- `models/qfr_m0.py`, `qfr_m1.py`, `qfr_m2.py`: separate nested model builders.
- `models/qfr_results.py` or `qfr_support.py`: structured results and independent budget/objective/balance recomputation.
- Separate v2 development fixtures and tests for domain validation, multi-item balances, cost accounting, and programmatic nesting.

The schema should use ordered unique item/scenario identities; exact key coverage; finite, strict R0 domains; exactly levels 0/1/2; complete η/cost/δ maps; and hashes over the whole realization. Development fixtures must be labeled non-formal and must not freeze future values.

### R2 may reuse unchanged

`io`, `runtime`, generic source/manifests, status, locking, canonical JSON, and existing CI skeleton. It may reference generic validation/result extraction techniques, but should not subclass old scientific data classes.

### R2 should not modify or implement

- Do not change old `model_data.py`, `mechanism_data.py`, M0/M1/M2, algorithms, old fixtures, old correctness evidence, or old scripts merely to make v2 fit.
- Do not implement EF, exact oracle, A0, A1_new, pilot, OOS, or formal experiments.
- Do not choose final parameter values, scenario distributions, seeds, scale tiers, tie-breaking policy beyond what R2 correctness requires, or statistical thresholds.
- Do not delete historical modules. Active v2 imports should be explicit and versioned.

## 4. R3–R8 handoff constraints

- **R3:** build new EF/exact oracle/A0 and a fresh correctness protocol; use old C&CG control invariants without inheriting old scientific adapters.
- **R4:** decide A1_new, implement it, and prove EF≈A0≈A1_new; old Memory has no default status.
- **R5:** adapt immutable runner/supervisor/replay for a preregistered v2 pilot and diagnose execution capacity.
- **R6:** freeze formal scientific parameters, seeds, OOS/statistical rules, and scale matrix; do not promote pilot defaults automatically.
- **R7/R8:** remain subject to the synchronized roadmap and explicit authorization; no R1 finding starts formal work.

## 5. Audit-only conclusion

The safest migration is additive: preserve old paths and their proofs, create an explicit v2 scientific namespace, and connect it to reviewed generic infrastructure through small adapters. This avoids both needless reimplementation of engineering controls and silent inheritance of obsolete mathematics.
