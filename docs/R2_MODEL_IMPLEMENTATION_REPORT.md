# R2 New M0/M1/M2 Implementation Report

Status: **R2 implementation delivery — ready for independent review after Draft PR creation**
Scope: model/schema implementation and model-level validation only; no R3 algorithm work

## 1. Source and governance anchors

R2 was created from clean synchronized `main` at commit `0a5c7de34d7ade0fea13554494ee7ce0178c0aab`, tree `57fd6cc2a4c528855845288e809347a5a7e1419b`. That commit is the user-approved active-roadmap synchronization after merged R1.

The implementation authority is the merged R0 scientific design together with the R1 reuse audit and impact map. The implementation commit/tree and Draft PR URL are external Git/GitHub anchors reported at delivery; they are not embedded in files covered by their own hash set.

R1 classifications remain exactly 39 `DIRECT_REUSE`, 29 `REUSE_WITH_MODIFICATION`, 85 `HISTORICAL_ONLY`, and 4 `REWRITE_REQUIRED`.

## 2. Implemented v2 path

The migration is additive. Old `model_data.py`, `mechanism_data.py`, `models/m0.py`, `models/m1.py`, `models/m2.py`, old algorithms, fixtures, scripts, and evidence remain unchanged under their historical paths.

| New asset | R1 mapping | R2 role |
| --- | --- | --- |
| `data/qfr_data.py` | `REUSE_WITH_MODIFICATION` schema pattern | Immutable ordered multi-item/multi-scenario schema with full `(d_iω, δ_iω)`, strict domains, deep freezing, full-data hash, and scenario hash |
| `models/qfr_common.py` | new scientific core required by `REWRITE_REQUIRED` old model cores | Shared linear sets, costs, variables, constraints, fixed-budget accounting, and explicit nesting restrictions |
| `models/qfr_m0.py` | additive rewrite of old M0 scientific meaning | M0=Q with item-indexed effective inventory and shortage recourse only |
| `models/qfr_m1.py` | additive rewrite of old M1 scientific meaning | M1=Q+F at base reliability `r=0` |
| `models/qfr_m2.py` | additive rewrite of old M2 scientific meaning | M2=Q+F+R with levels `{0,1,2}` and F-specific reliability |
| `models/qfr_support.py` | `REUSE_WITH_MODIFICATION` accounting pattern | Independent loaded-solution validation and reconstruction of all v2 costs, balances, fulfillment, budgets, and objective |
| R2 fixture/tests | separate v2 development evidence | Strict schema, structure, accounting, nesting, invalid-solution, linearity, and licensed solve coverage |

No `DIRECT_REUSE` production file was modified. Generic hashing and locked runtime/solver infrastructure are imported unchanged.

## 3. Scientific model implementation

The schema supports nonempty ordered item and scenario sets with exact key coverage. It validates finite values and the frozen domains for `B`, `τ`, `c_i^Q`, `h_i`, `a_i`, `bar F_i`, `c_i^F`, `c_ir^R`, `η_ir`, `p_i^F`, `s_i`, `d_iω`, and `δ_iω`. Reliability levels are exactly `(0,1,2)`; both reliability mitigation and premium have strict frozen ordering.

All models are finite-scenario two-stage formulations. Q/F/z are scenario-independent first-stage variables; x/u are scenario-indexed second-stage variables. There is one representative flexible channel per item and no supplier index.

- M0 contains only Q, u, and θ. Its cash budget contains `C_Q` and excludes shortage loss.
- M1 contains Q, base-level F/z, x, u, and θ. At `r=0`, fulfillment is `(1-δ_iω)F_i` and reliability premium is zero.
- M2 contains Q, `F_ir`, `z_ir`, x, u, and θ. It enforces at most one level, `F_ir <= bar F_i z_ir`, and linear fulfillment `x_iω <= Σ_r[1-(1-η_ir)δ_iω]F_ir`.

For every model and scenario, the same fixed total budget covers pre-disaster real spending plus actual flexible exercise. Shortage loss is excluded from cash budget and included in the worst-scenario objective epigraph. No budget is forced to be exhausted.

The implementation contains no dynamic perishability, supplier selection, multisourcing, DRO/Γ/ambiguity set, demand-disruption correlation parameter, emergency fund, option fee, `y_F`, `K_F`, or reliability protection for Q.

## 4. Programmatic nesting evidence

Two explicit construction restrictions support automated nesting tests:

1. `build_qfr_m1(data, disable_f=True)` fixes all base-level F/z to zero. Capacity then forces x=0, both F and R spending are zero, and the remaining Q/u/budget/objective projection is M0.
2. `build_qfr_m2(data, reliability_levels=(0,))` constructs the exact base-level M2 restriction. Automated signatures confirm identical variables, constraint components, coefficients, bounds, and objective coefficients to M1.

Licensed tests solve M0, M1|F=0, M1, and M2|R={0} on the same three-item development fixture. They validate equal nested optimal values and independently reconstruct the loaded solution accounting. These are R2 model-level nesting tests, not EF/A0 correctness evidence.

## 5. Validation and test evidence

The only numerical fixture is marked `TEST_FIXTURE_ONLY_NOT_FORMAL_SCIENTIFIC_PARAMETERS`. It represents three heterogeneous item profiles solely to exercise the unified schema and model; it does not freeze formal values.

Environment preflight:

- CPython 3.12.10
- Pyomo 6.10.1
- gurobipy 13.0.2
- Gurobi Optimizer 13.0.2
- `gurobi_direct`
- Threads=1
- solver/license available: PASS
- no fallback

Test results:

- Focused R2 solver-free: `64 passed, 2 deselected`
- Focused R2 licensed: `2 passed, 19 deselected`
- Full solver-free regression: `794 passed, 102 deselected`
- Full licensed regression: `102 passed, 794 deselected`

The first focused solver-free run exposed one incorrect test expectation about Pyomo eliminating fixed-zero variables from a standard representation. The test was corrected to validate zero F/R spending directly; no scientific equation changed.

## 6. Scope audits

- Git scope: only additive v2 implementation/tests/delivery assets; no old scientific or `DIRECT_REUSE` files changed.
- Scientific symbols: no old F-OPTION or old Q-protecting Reliability appears in the active v2 implementation.
- Single-item assumptions: the v2 schema, variables, constraints, recourse, and accounting are item-indexed and tested on three items.
- Budget: independent recomputation separates cash expenditure from shortage loss for every model/scenario.
- Nesting: both frozen degeneration relations have solver-free structural and licensed behavioral tests.
- No scope creep: EF, exact oracle, A0, A1_new, pilot, OOS, formal design, and experiments were not implemented or executed.

## 7. Known limitations and deferred work

- R2 provides builders and independent loaded-solution validation, not a new production solve/certificate workflow. EF, exact recourse/oracle, A0, correctness protocol, tie policy, and replay certificates belong to R3.
- Redundant z labels at F=0 remain permitted by the frozen specification. The explicit nesting restriction fixes them to zero only to expose the economic projection cleanly.
- Formal calibration, scenario generation, seeds, scale thresholds, OOS sizes, repetitions, and statistical settings remain unfrozen.
- A1_new remains completely unfrozen and deferred to R4.

Scientific runs = 0. Pilot runs = 0. Formal experiments = 0. No scientific-result or algorithm-performance claim is made.
