# Legacy Reuse & Impact Audit v2

Status: **R1 audit deliverable — no scientific implementation**  
Classification date: 2026-08-29  
Authority: the merged R0 v2 documents, not filenames or old milestone labels

## 1. Audit baseline and scope

The audited base is `main` commit `77b4fa1ac97f3f7405c719b6cd004f38c2b9e3ab`, tree `60b12aa9e3e8d01d0499a5218f0fa30102e8e331`. PR #11 is `MERGED`; its final head is `a4777d2a223099a8bf01584500d7289bdcb1a1d0` and its merge commit is the audited base. PR #10 is merged. PR #9 is closed without merge, and its six exclusive commits are not ancestors of this base.

The audit covered all 157 tracked files: 47 package files, 39 tests, 6 scripts, 2 configs, 56 documents/evidence files, CI, packaging, requirements, and the experiment placeholder. Implementations and their import/data dependencies were inspected. Ignored local `outputs/` and `artifacts/` are runtime material, not tracked repository assets and are not silently promoted into this inventory.

The classification unit is the named asset or sub-asset. A file can contain a reusable integrity primitive and an old scientific wrapper; such a file is classified at the safer whole-file level, while reusable sub-assets are named explicitly. `DIRECT_REUSE` means reusable engineering semantics, not scientific validation of v2.

## 2. Classification meanings

- **DIRECT_REUSE (A):** scientifically neutral and usable without changing its semantics.
- **REUSE_WITH_MODIFICATION (B):** useful structure exists, but its interface, authority binding, or scientific adapter must change for v2.
- **HISTORICAL_ONLY (C):** retained as provenance/regression evidence and excluded from the active v2 scientific path.
- **REWRITE_REQUIRED (D):** its governing mathematics conflicts with v2; adapting it in place presents unacceptable leakage risk.
- **UNCLEAR / NEEDS_DECISION (E):** a later scientific or governance choice is required. R1 does not make it.

## 3. Scientific v2 baseline used for every decision

The active model is heterogeneous-material, finite-scenario, two-stage Q-F-R allocation. Stage 1 chooses physical prepositioning `Q_i`, flexible-capacity reservation `F_ir`, and level selection `z_ir`. Stage 2 chooses actual flexible procurement/production `x_iω` and shortage `u_iω`. Reliability reduces disruption loss only for F through `1-(1-η_ir)δ_iω`.

For every scenario, the same fixed budget covers `C_Q + C_F + C_R + C_ω^E <= B`; shortage loss is in the objective and never in the cash budget. Scenarios carry item-indexed demand and flexible-supply disruption `(d_iω, δ_iω)`. The nested models are M0=Q, M1=Q+F at base reliability, and M2=Q+F+R. These names do not preserve the v1 meanings.

## 4. Dependency map of the current active code

The old scientific execution path is tightly connected:

`pilot.configuration -> OptionData -> m0/m1/m2 -> algorithms.common -> extensive_form/exact_oracle -> standard_ccg/memory_guided_ccg -> pilot.measurement -> pilot.replay/restart`.

By contrast, the engineering leaves under `io/`, `runtime/`, most of `reproducibility/`, and `statistics/` do not import model or pilot science. This boundary is why generic infrastructure can be retained while model-specific builders, recourse, certificates, and configurations cannot be called v2-ready.

## 5. Repository inventory and classification

### 5.1 DIRECT_REUSE

| Asset | Verified reusable role | Limits |
|---|---|---|
| `io/hashing.py` | Canonical JSON and SHA-256 | Arrays remain order-sensitive; `1` and `1.0` are not canonicalized as the same number. New schemas must choose types consistently. |
| `io/atomic.py` | Same-directory temporary files, bounded atomic replace, JSON/text/CSV writes | The gzip path includes flush/fsync; ordinary text helpers do not claim power-loss durability. |
| `io/locking.py` | Bounded cross-process locking | Stale-lock behavior is the library's acquire semantics, not arbitrary lock deletion. |
| `runtime/environment.py`, `runtime/solver.py`, `runtime/status.py`, compatibility `environment.py` | Fail-fast environment facts, process-level preflight cache, no-fallback Gurobi construction, exact status normalization | Runtime lock is exact Python 3.12.10 even though the R1 brief says 3.12.x. R1 does not change it. |
| `reproducibility/git_state.py` | Required-file and protected-root source validation | The default root can be broad; production callers must continue passing the package root rather than all `src/`. |
| `reproducibility/manifests.py` | Source/environment/input manifest and seal construction | A builder is not a cleanliness validator; it must remain composed with source validation. |
| `reproducibility/test_evidence.py` | PR #10 testcase-level JUnit verification | Requires actual executed test cases and checks outcomes, declarations, counters, hash, and exit status. |
| `statistics/cvar.py`, `bootstrap.py`, `multiple_testing.py` | Pure CVaR, deterministic paired bootstrap, Holm helpers | Their default confidence/alpha/resample counts are API defaults, not frozen v2 scientific parameters. |
| `.github/workflows/ci.yml`, `configs/solver.yaml`, requirements files, `.gitignore` | Solver-free/licensed split and locked toolchain skeleton | Licensed CI is conditional; no license success was claimed by R1. |
| PR #10 integrity primitives | JUnit testcase validation, mandatory EF/A0/A1 audit fields, full inner/outer source binding, bounded archive replacement, production-entry regression | Existing N6 wrappers and method names still require versioned v2 adapters. The hardening itself is retained. |
| Generic tests for the above | Engineering regression evidence | They validate infrastructure, not v2 mathematics. |

`pilot/heartbeat.py` is also direct-reuse infrastructure: bounded read conflict handling, monotonic deadlines, exception context, and fail-closed behavior are model-neutral. The known historical 7-versus-8 conflict-count test event remains a non-blocking timing-sensitive test note; the production semantics were not shown wrong, and R1 does not alter it.

### 5.2 REUSE_WITH_MODIFICATION

| Asset | Preserve | Modify before active v2 use |
|---|---|---|
| `data/model_data.py` | Immutable validated-schema pattern, exact key checks, deterministic ordering, hashes | New item-indexed schema and strict v2 domains; remove `resource_id` single-item contract, suppliers, scalar demand/cost/penalty, and old fulfillment. |
| `data/mechanism_data.py` | Nested immutable mapping and serialization techniques | Do not inherit `ReliabilityData`/`OptionData`; replace old levels, premiums, fulfillment, option fee/cap, and emergency prices with the v2 Q-F-R fields. |
| Model construction/result support patterns | Separation of builders from solver runtime, finite-value checks, independent result accounting | New result names and item/scenario dimensions; new feasibility checks and v2 cost reconstruction. Old model equations are rewrite-required. |
| `algorithms/common.py` | Solver/audit envelope and primal feasibility checking patterns | Replace `OptionData`, old first-stage decision, subset construction, protocol authority, and fixing/summarizing adapters. Note that old epigraph `eta` is unrelated to new reliability `η_ir`. |
| EF scenario-expansion shell | Finite-scenario expansion and objective epigraph pattern | New v2 model constraints, multi-item results, and new correctness authority/evidence are required. |
| Exact-oracle enumeration/certificate shell | Complete ordered enumeration, deterministic worst-case tie break, completeness certificate pattern | Recourse mathematics, decision hash, raw result schema, and verification must be rewritten. |
| Standard C&CG control loop | Active-set loop, LB/UB ownership, full-oracle-only certification, duplicate/progress guards, trace concepts | Use a v2 model adapter and new protocol. Do not reuse old master/oracle/certificate records as v2 evidence. |
| A1 record/timing/interface hooks | Iteration records, candidate container concepts, full certification boundary, replay hooks | Only after A1_new is selected. Memory, ranking, phases, scores, and state machine are not inherited. |
| `pilot/storage.py`, supervisor portions of `pilot/execution.py`, source-object archive primitives | Immutable run directories, lineage, manifests, process cleanup, bounded heartbeat supervision, authenticated Git objects | Split generic execution from N6 methods/protocols and bind it to new v2 source/config authorities. |
| `pilot/replay.py`, `restart.py` | Hash/inventory/source/JUnit/integrity checks, fail-closed batch progression | Replace fixed N6 methods, old generated data, five-method grouping, old protocols, and old scientific verification. |
| `pilot/measurement.py`, `summary.py` | Timing/counter collection and descriptive aggregation patterns | Old `y_F`, paid-supplier, Option, scalar quantity, and fixed projection assumptions must be replaced. |
| Correctness and pilot scripts | No-overwrite CLI orchestration and source-gate pattern | New scripts must target new modules and authorities; old scripts stay unchanged for historical replay. |
| `pyproject.toml`, package `__init__` files, `README.md`, `STATUS.md`, `experiments/README.md` | Packaging/project entry structure | Public descriptions and exports are old-route/stale. Update only under separately governed provenance because historical hash manifests currently bind some files. |
| `docs/PROJECT_ROADMAP_v2.md` | R0 roadmap structure and governance principles | Its milestone meanings conflict with the latest authorized R1 audit/R2–R6 sequence. Synchronize it under explicit governance before any R2 implementation starts. |

### 5.3 HISTORICAL_ONLY

- All v1 research/model/algorithm/experiment/roadmap/open-decision documents and v1/N0 hashes.
- N1–N6 reports, protocols, authorizations, frozen hashes, compact evidence, object archives, and scientific summaries.
- Specifically, `docs/N6_PRELAUNCH_REVALIDATION_v2.md` is an old-route execution authorization bound to `n6pilot02`, the old protocol/config, 16 configurations, 80 runs, old seeds/budgets, and old M0/M1/M2/EF order. Its `v2` filename does not make it a Q-F-R asset.
- Old development fixtures and their correctness evidence for N2–N5.
- `configs/pilot/n6_candidates.json` and all old budgets, seeds, scenario counts, distributions, premiums, option parameters, and risk settings.
- Old Memory-Guided Three-Phase C&CG mechanism and its N5/N6 numerical results. Its code remains executable for historical replay, but is not an A1_new definition.
- Old N6 equality and mechanism results. They are evidence that the old route was executed and audited, not v2 correctness evidence.
- Transition/R0 traceability records as provenance. The v2 R0 documents themselves remain the current scientific authority and are not superseded by this audit.

HISTORICAL_ONLY does not authorize deletion, movement, re-hashing, or reinterpretation. Existing tests that validate frozen evidence remain valuable engineering regression tests.

### 5.4 REWRITE_REQUIRED

| Asset | Why in-place adaptation is unsafe |
|---|---|
| `models/m0.py` scientific core | It optimizes supplier quantities with scenario fulfillment, scalar served/shortage/unused variables, and no `a_i`, `h_i τ`, or heterogeneous items. v2 M0 is item-indexed physical Q. |
| `models/m1.py` scientific core | Old M1 adds reliability protecting Q. New M1 adds flexible capacity F at base reliability. The same name masks a different mechanism. |
| `models/m2.py` and old result accounting | Binary `y_F`, `K_F`, monetary option cap, emergency `g/E`, and old Reliability are incompatible with continuous reserved `F_ir`, level `z_ir`, and R protecting F. |
| Old recourse in `exact_oracle.py` | The scalar closed form independently minimizes emergency purchase. V2 has item-indexed recourse coupled by the shared per-scenario budget, so independent scalar clipping is invalid. |
| Model-specific EF constraints/certificates | They are precisely old M2, including old variable names and balances. Framework concepts may be adapted, but equations and scientific certificates must be new. |
| Old scenario generator | It generates scalar demand, supplier-level fulfillment, and scenario emergency price; it does not generate item-indexed `(d_iω, δ_iω)`. |
| Old candidate score and old recourse ranking | They use scalar shortage after supplier deliveries and the old emergency path; they have no scientific authority for v2. |

These components should be left intact under their historical paths. New v2 modules are safer than replacing them because evidence tests bind current old files to committed source and hashes.

### 5.5 UNCLEAR / NEEDS_DECISION

1. **A1_new mechanism:** candidate ranking, acceleration method, and whether any memory concept exists are deliberately unfrozen until R4.
2. **Recourse implementation strategy:** R2/R3 must decide whether the multi-item shared-budget recourse is represented directly as an LP, by a validated closed form if one is proved, or through another exact formulation. R1 does not select one.
3. **Representative recourse solutions and tie breaking:** multiple second-stage optima can have equal cost. Result/certificate policy must be frozen before correctness evidence.
4. **Scenario identity and generation:** the schema minimum is ordered items plus `d_iω` and `δ_iω`; distributions, correlation treatment, sizes, and seeds remain later decisions.
5. **Formal statistical/calibration values:** budget grids, scale thresholds, repetitions, OOS sizes, alpha, and bootstrap counts are not inherited from defaults or N6.
6. **Documentation/hash migration:** root README and STATUS are stale but are bound by historical manifests. A later governance step must update active entry points without silently invalidating history.
7. **Roadmap numbering:** merged `PROJECT_ROADMAP_v2.md` describes R1–R8 differently from the latest explicit R1 audit/R2–R6 instructions. The latest explicit sequence is the operational authority for this impact map. The roadmap is therefore `REUSE_WITH_MODIFICATION`, and authorized synchronization is a hard governance gate before R2 implementation. R1 does not edit the frozen R0 file.

## 6. Model-layer impact and multi-item audit

### Current M0

Reusable: builder/runtime separation, deterministic sets, epigraph pattern, validation/extraction techniques. Not reusable as v2 science: supplier-indexed Q, scalar demand, scenario delivery rate, served `x`, unused `h`, procurement limit, and the old cost formula. `x` and `h` also change meanings in v2: `x_iω` is actual flexible exercise, while `h_i` is a preservation-cost parameter.

### Current M1

Old M1 is **Q + Reliability**. New M1 is **Q + F at r=0**. Old binary level selection, exactly-one supplier level, fixed/unit premiums, and reliability-modified Q delivery are not a base for new M1 equations.

### Current M2

Old M2 is **Q + Reliability + binary F-OPTION**. New M2 is **Q + flexible-capacity reservation + F-specific Reliability**. `y_F`, `K_F`, old `option_cap`, emergency `g/E`, supplier reliability, and the old balance must not enter the new execution path.

### Missing v2 structures

The current implementation lacks all of the following as active v2 structures: ordered item set, `h_i`, `a_i`, `τ`, `F_ir`, `z_ir`, fixed levels `{0,1,2}`, `η_ir`, `δ_iω`, `bar F_i`, `c_i^F`, `c_ir^R`, `p_i^F`, item-indexed `x_iω/u_iω`, and item-indexed per-scenario budget accounting. It also lacks v2 programmatic nesting tests.

### Single-item dependency points

- Data: `resource_id` says exactly one resource; demand and penalty are scalar by scenario.
- Models/results: q is supplier-indexed; x/u/h/g/E are scalar by scenario.
- Recourse/oracle: one demand, one delivered amount, one emergency price, one monetary cap.
- Candidate ranking: scalar shortage-loss score.
- Pilot generation/measurement/summary: scalar quantities and old Option activation.
- Certificates/replay: raw fields and balance checks encode those scalar variables.

Generic JSON, maps, traces, lists, and hashes naturally carry multi-item payloads, but that serialization ability is not a multi-item scientific implementation.

## 7. Scenario and uncertainty migration direction

The smallest safe new scenario schema has deterministic ordered `items` and `scenarios`, and for every scenario complete item-keyed maps `d[ω][i]` and `delta[ω][i]`. It must validate finite values, `d>=0`, `0<=delta<=1`, exact key coverage, stable identities/order, and include the entire realization—not merely a base projection—in its scenario hash. Static v2 parameters belong in the full data/config hash.

Current canonical JSON/hashing can encode this representation. Current scientific scenario identity cannot: `BudgetAllocationData.scenario_sha256` contains scalar demand and base supplier fulfillment; the N6 wrapper adds level fulfillment and emergency price. Neither is the v2 realization.

## 8. EF, A0, and A1 conclusions

### EF — REUSE_WITH_MODIFICATION framework; REWRITE_REQUIRED equations

Current EF delegates directly to old `build_m2`. Finite-scenario expansion, epigraph aggregation, exact solve wrapping, and audit layout are useful patterns. All model equations, extraction fields, and v2 certificates must be rebuilt. Old EF values are not v2 evidence.

### A0 — REUSE_WITH_MODIFICATION

The active-set control loop correctly separates MP-derived LB from full-exact-oracle UB/certification, tracks signed/nonnegative gaps and violations, guards duplicates, and terminates fail-closed. This is valuable. It directly imports old M2 subset builders, first-stage decisions, recourse, protocols, and trace verification, so it is not drop-in reusable. R3 should preserve the reviewed control invariants behind a v2 adapter while rebuilding master, recourse/oracle, trace schema, and certificates.

### A1 — historical mechanism; reusable hooks only

Memory inspection, candidate ranking, scalar score, eligibility, and the three-phase state machine are HISTORICAL_ONLY. Iteration-record, timing, candidate-container, and complete-certification hooks may be adapted after A1_new is chosen. No audit finding selects, restores, renames, or endorses old Memory.

## 9. Correctness evidence

Old evidence has **engineering validity**: immutable files, source proofs, seals, JUnit evidence, trace replay, and failure semantics remain useful tests of the repository. It does not establish **scientific correctness for v2**.

V2 must generate fresh evidence for:

1. M1 with F disabled equals M0;
2. M2 restricted to base reliability equals M1;
3. EF approximately equals A0 under a newly frozen v2 correctness protocol;
4. EF approximately equals A0 and A1_new after A1_new is frozen.

## 10. Experiment, OOS, and statistics

Seed handling, canonical configuration hashes, immutable run IDs, failure normalization, lineage, locking, timing boundaries, and source manifests are reusable with versioned adapters. The current repository has **no implemented independent OOS evaluator** and no formal v2 experiment runner. OOS therefore requires later implementation rather than migration of a nonexistent module.

Bootstrap, Holm, and CVaR computations are directly reusable as pure helpers. Old numerical settings, seeds, budgets, scenario counts, distributions, old F parameters, premiums, and results are historical only. N6 projection formulas are descriptive implementation patterns, not a formal v2 scale design.

## 11. Environment and CI

The repository currently locks CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, `Threads=1`, and no fallback. R1 neither installed nor reconfigured anything and ran no solver. One complete solver-free run selected 730 tests: 730 passed, 100 Gurobi-marked tests were deselected, and three JUnit-property warnings were emitted by the Windows heartbeat stress parametrization.

Licensed status was not inferred from installed package metadata. The preflight remains the only accepted licensed environment proof before future solves.

## 12. Final reuse summary

- Maximize reuse of independent I/O, hashing, locks, source validation, manifests, environment/status, test-evidence, statistics, CI, immutable storage, and audit primitives.
- Reuse C&CG, supervisor, replay, and run orchestration as reviewed patterns behind new versioned scientific adapters.
- Preserve all old code/evidence for historical replay; never treat old equality or pilot results as v2 evidence.
- Implement v2 scientific data, M0/M1/M2 equations, multi-item recourse, scenario schema, and scientific certificates in new modules.
- Defer A1_new, numerical calibration, experiment scale/OOS sizes, and final inferential choices to their authorized stages.

No scientific code, model, algorithm, fixture, parameter, or evidence was changed by R1.
