# R3 v2 Correctness Numerical Protocol

Status: `FROZEN_BEFORE_FIRST_LICENSED_CORRECTNESS_RUN`

Scope: R3 — EF + Standard C&CG Correctness for the heterogeneous-material Q-F-R v2 model family (`M0=Q`, `M1=Q+F`, `M2=Q+F+R`).

This protocol was frozen on the clean R3 base commit `d5484adff21040bdaa0aaa3e727c9d341b342e47`, tree `30d3e0ed261b794de8420bd9bd1c0d9873ee4e29`, before any R3 licensed correctness comparison. Its identity is the SHA-256 of the exact UTF-8 file bytes in the protocol-freeze commit.

## 1. Authority and provenance

The numerical and deterministic rules below originated as generic rules in the historical N4 protocol. On 2026-08-29 the user explicitly re-registered them for R3 v2 correctness. They are therefore a newly frozen R3 v2 protocol, not an automatic inheritance of the old scientific protocol.

Nothing in this document imports the old Q-R-F model, F-OPTION, old Reliability semantics, old fixtures, scenarios, data, scientific parameters, EF/A0/A1 evidence, or conclusions. Only the rules stated here are authoritative for R3.

No tolerance, fixture, or acceptance rule may be changed after observing R3 correctness results merely to obtain acceptance. A genuine protocol defect requires a new version, preserved prior artifact and run provenance, an impact statement, and reruns of every affected case.

## 2. Numerical comparison rule

For finite real numbers `a` and `b`, define the objective-currency threshold

`T(a,b) = 1e-7 + 1e-9 * max(1, abs(a), abs(b))`.

All compared quantities and bounds must be finite. EF and A0 objective values agree only when `abs(Z_EF-Z_A0) <= T(Z_EF,Z_A0)`. The reported relative difference is `abs(Z_EF-Z_A0) / max(1,abs(Z_EF),abs(Z_A0))`.

The same `T` rule is used wherever this protocol expressly calls for a numerical comparison. It does not turn near-equal scenario losses into exact ties and does not permit omitted constraint violations.

## 3. Solver and accepted status

Every licensed EF, restricted-master and exact-recourse solve uses:

- Python 3.12.10;
- Pyomo 6.10.1;
- gurobipy and Gurobi Optimizer 13.0.2;
- `gurobi_direct`;
- `Threads=1`;
- no fallback;
- `MIPGap=0`;
- `MIPGapAbs=0`;
- `FeasibilityTol=1e-9`;
- `OptimalityTol=1e-9`;
- `IntFeasTol=1e-9`.

Only `SolverStatus.ok` paired with `optimal` or `globallyOptimal` is a correctness success. Every accepted solve must have finite primal objective and solver bound. A time limit, interruption, infeasibility, unboundedness, warning, error, unknown status, missing result, or nonfinite value fails closed.

## 4. Canonical scenarios, identity and ties

Input scenario IDs are unique strings. Their declared order remains part of data provenance. Canonical scenario order is ascending Python string (Unicode code-point) order, independent of locale, filesystem order, hash randomization, solver result, or desired iteration count.

The initial restricted-master pool contains exactly the smallest canonical scenario ID.

Every exact oracle evaluates every scenario in the complete original finite `Omega`, in canonical order, on the same fixed first-stage decision. The exact worst loss is the numeric maximum of these exact recourse optima. If multiple scenario values are exactly equal as Python finite floats, the smallest canonical ID is selected. Near-equal but unequal values are not ties; tolerance is used for acceptance, not for replacing the true maximum.

Restricted-master membership is deduplicated by complete v2 scientific scenario identity. Identity includes the complete item-indexed demand and disruption realization `(d_iw, delta_iw)` and the current QFR schema/data identity. Scenario ID alone is not sufficient. Distinct IDs with identical scientific realizations are duplicates and cannot both be added. Two realizations with the same index but different demand, disruption, or static QFR data must not validate against each other.

## 5. EF benchmark

For each preregistered case and each model kind M0/M1/M2, EF uses the reviewed R2 builder on the entire finite scenario set. All first-stage variables are shared across scenarios and second-stage variables are scenario indexed. EF may not alter the R2 model equations or accounting.

An accepted EF result contains the full v2 model/data/scenario identity, solver/config/protocol/source identity, objective and bound, first-stage decision, full-scenario accounting and feasibility validation.

## 6. A0 Standard C&CG

A0 is standard exact finite-scenario C&CG without memory, candidate ranking, shortlist, heuristic screening, approximate oracle, learned state, or A1 mechanism.

For iteration `k`:

1. Solve the reviewed R2 model restricted to the active scientific scenario pool.
2. The accepted restricted-master optimal objective is the formal `LB_k`.
3. Fix the returned first-stage Q/F/z decision and solve exact recourse for every original scenario.
4. Let `Q_worst_k` be the exact maximum recourse loss and let `C_pre_k` be that decision's first-stage cost. The candidate upper bound is `U_k=C_pre_k+Q_worst_k`.
5. Only a complete successful full oracle may update the formal incumbent UB. `UB_k=min(UB_{k-1},U_k)`; an exactly equal candidate retains the earlier incumbent and its evidence.
6. Record the signed gap `g_k=UB_k-LB_k` and reported gap `max(0,g_k)`.
7. Certify only after the iteration's full exact oracle if both the global bound condition and current maximum violation condition pass.
8. Otherwise add the canonical exact-worst scientific scenario if it violates the current epigraph/feasibility threshold and is not already represented. If the exact worst is already represented, or no new violating scenario exists while the gap fails, return `convergence_failure`; never repeat a scenario or clip bounds.

A solver bound, master epigraph value, candidate score, heuristic score, or partial oracle is never a formal UB.

## 7. Convergence and violation

Convergence requires

`-T(UB_k,LB_k) <= UB_k-LB_k <= T(UB_k,LB_k)`.

Larger negative crossing is a numerical failure rather than a value to clip away.

For the current restricted-master decision and its just-completed full oracle, define maximum epigraph violation as `max(0,max_w Q_w(x_k)-theta_k)`. It passes only when it is no greater than `T(max_w Q_w(x_k),theta_k)`. All separately checked variable bounds, integrality, demand, capacity, fulfillment, budget and accounting equalities must also pass their corresponding `T` comparison and the locked solver feasibility policy.

Both global gap and current maximum violation must pass. Equality of objective values alone is insufficient.

## 8. Iteration safety

The maximum iteration count is `len(Omega)+1`. This is only a fail-closed safety bound. Exhaustion without certified convergence returns `iteration_limit` and is not accepted. A smaller explicit positive limit is allowed only in a preregistered negative/failure test and cannot certify correctness.

Every successful master iteration performs exactly one complete finite-scenario oracle before any convergence decision. Partial oracle failure cannot update UB or certify convergence.

## 9. EF/A0 acceptance

Each preregistered positive case passes only if all of the following hold:

- EF and every A0 solve have accepted status and complete finite evidence;
- EF and A0 objectives agree under `T`;
- A0 is certified by the frozen gap and violation rules;
- each reported first-stage strategy is independently feasible across all scenarios under the reviewed R2 accounting;
- fixed total budget and shortage/objective accounting validate;
- exact-oracle worst value and deterministic tie result replay;
- ordered pool additions contain no duplicate scientific identity;
- all required identities, hashes, traces and audit fields validate;
- replay of both EF and A0 evidence succeeds.

Multiple optimal first-stage solutions are legitimate. Arbitrary solver-selected variable vectors or worst IDs need not match across EF and A0 when each solution separately satisfies the complete objective, feasibility, oracle and provenance checks.

## 10. Evidence and replay contract

Evidence binds at least:

- R3 execution commit and tree plus relevant source-file hashes;
- R2 model base/version and source identity;
- exact protocol SHA-256;
- canonical fixture/config/data/scenario SHA-256 identities;
- complete item and scenario order/identity;
- solver versions, interface, options, status and termination;
- method and model kind;
- initial scenario and ordered pool additions;
- every master LB/status/decision and every full-oracle scenario result;
- candidate and incumbent UB ownership;
- signed/reported gap, thresholds, violation and convergence decision;
- final first-stage decision, objective, accounting and feasibility;
- certificate status and replay result.

Validation is fail-closed and rejects missing or altered source, protocol, config, data, scenario, objective, bound history, pool order, oracle completeness, solver status, or mandatory audit fields. The loaded evidence must bind to the exact QFR data used to construct the model.

## 11. First-run and failure governance

The first licensed EF/A0 comparison after this protocol-freeze commit must be retained whether it passes or fails. A failure must be classified as an EF bug, A0 bug, R2 model blocker, protocol-implementation bug, or solver/numerical anomaly. It may not be hidden by changing tolerance, solver options, fixture, scenario, or recorded history.

If a genuine R2 model inconsistency is exposed, R3 stops without silently changing the reviewed scientific model. Ordinary R3 implementation defects may be repaired in the same R3 PR while preserving the first failure provenance.

## 12. Scope exclusions

This protocol authorizes no A1_new design or implementation, memory, ranking, heuristic oracle, pilot, formal experiment, OOS scientific evaluation, performance claim, scientific retuning, or modification of the frozen Q-F-R model. Correctness fixtures are test-only inputs and are not formal scientific parameters.
