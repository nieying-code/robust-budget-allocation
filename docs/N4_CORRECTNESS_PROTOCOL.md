# N4 correctness protocol v1 — pre-result freeze

This protocol is committed before N4 implementation or EF/A0 correctness results
are run. N0 specifies the required gates, not their numerical constants. No N0
model, N1 runtime, or N2/N3 scientific implementation is changed by this protocol.
Scope: single-resource M2, finite Omega, development/correctness evidence only.
The protocol remains fixed through N4 and N5; N7 cannot redefine it retrospectively.

## Numerical acceptance

Define T(a,b)=1e-7 + 1e-9*max(1,abs(a),abs(b)), in objective currency units.
All compared quantities and bounds must be finite.

- EF/A0 objectives agree iff abs(Z_EF-Z_A0)<=T(Z_EF,Z_A0).
- Report relative difference as abs(Z_EF-Z_A0)/max(1,abs(Z_EF),abs(Z_A0)).
- Global signed gap is UB-LB; reported gap is max(0,UB-LB). Accept only if
  -T(UB,LB)<=UB-LB<=T(UB,LB). Larger bound crossing is numerical failure.
- Maximum violation is max(0,max_w Q_w(x)-eta), measured for the current master
  decision and its just-completed full oracle. Accept iff it is <=T(max Q,eta).
- Feasibility/accounting checks use the same absolute/relative rule, binary and
  zero checks use T(value,0). No NaN/Inf or materially negative cash is accepted.
- Solver: Python 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct,
  Threads=1. N1 cached preflight and real license check precede timed work.
- Each EF/master/recourse solve uses MIPGap=0, MIPGapAbs=0, FeasibilityTol=1e-9,
  OptimalityTol=1e-9, IntFeasTol=1e-9. Only SolverStatus.ok paired with optimal or
  globallyOptimal is eligible. Finite primal objective and solver lower bound
  must agree within T and the loaded solution must pass feasibility checks.
  locallyOptimal, errors, unknown/invalid, limits, infeasible and unbounded states
  never certify success. Solver defaults are not a relaxation of this rule.

## Ordering and equivalent optima

- Input scenario IDs are unique strings, with their original declared order
  retained in data/hash provenance. Canonical ID order is ascending Python string
  (Unicode code-point) order, with no locale, randomized seed or outcome dependence.
- A0 starts with exactly the smallest canonical scenario ID. Active sets are
  deduplicated and stored in canonical order. Every oracle evaluates *all* original
  Omega scenarios, in canonical order, regardless of active set.
- The worst value is the numeric maximum of all exact scenario loss values.
  Among IDs with exactly equal maximum values choose the smallest canonical ID.
  Near-equal but unequal values are not substituted for the true maximum. Numerical
  acceptance tolerances do not reduce the maximum or hide an omitted violation.
- No new first-stage lexicographic objective is introduced. Multiple optimal
  q/z/y vectors are legitimate. EF/A0 comparison requires objective equality and
  separately certified all-scenario feasibility/recourse of each returned vector,
  not equality of arbitrary solver-selected vectors or worst IDs across different
  vectors. On hand cases with unambiguous decisions, also compare those decisions.
- Canonical single-resource recourse at fixed first stage uses minimal emergency
  quantity among economic minimizers. If p<s, g=min(max(d-R,0),F_bar*y/p,
  max(B-first_cost,0)/p); if p>=s, g=0. Then x=min(d,R+g), u=d-x, h=R+g-x.
  This is a representative of the existing recourse LP, not a new scientific
  objective. Each oracle scenario is actually solved with the locked solver and
  its optimum must match this independently computed value. Raw solutions remain
  in the audit. In particular, p=s ties choose g=0 without changing Q_w.

## Bounds, incumbents and convergence

The restricted master uses the unchanged M2 builder on the selected scenarios,
including the explicit first-stage cash constraint. All omitted scenario recourse
is relatively complete through shortage, so it is a relaxation of full M2.

LB_r is the maximum of accepted restricted-master solver lower bounds through r.
Record the master primal objective separately. Do not use a nonoptimal master or
its possibly feasible primal objective as an exact lower bound.

For the current feasible first-stage x_r, a complete successful oracle gives
U_r=first_cost(x_r)+max_{w in Omega} Q_w(x_r). Only this quantity can update UB.
Keep the smallest U_r and its entire corresponding first-stage/oracle evidence;
on exactly equal UB retain the earlier incumbent. A solver's bound is never UB.

Every successful master iteration performs exactly one complete Omega oracle
before any convergence decision. Failure during an oracle is explicitly partial,
cannot update UB and cannot certify convergence. No subset, heuristic, memory,
candidate screening, warm-start transfer or three-phase logic is allowed.

Certify A0 only after this iteration's full oracle if BOTH global gap and current
maximum violation pass. The returned incumbent remains bound to the full oracle
that generated its UB; the final current-master oracle is separately retained.
If not certified, add the exact canonical worst ID when violation exceeds its
tolerance and it is absent. If it is already active, or no violating new scenario
exists while the gap fails, return convergence_failure (never repeat a scenario).

Default maximum iterations is len(Omega)+1. An explicitly supplied positive
integer limit may be smaller for failure testing. Exhaustion returns iteration_limit,
not convergence; it does not change tolerances. Solver time limits likewise fail.

## Trace, failure and evidence

Trace each iteration's active IDs, master status/primal/bound/eta/first stage,
current full oracle and all per-scenario values, worst ID/loss, candidate UB,
global incumbent UB and producing iteration, LB, signed/accepted gap, violation,
thresholds, added scenario, statuses, runtime and certification decision.

Distinct terminal states include optimal (validated EF), certified (A0),
solver_error, infeasible, unbounded, time_limit, iteration_limit,
numerical_failure, oracle_failure and convergence_failure. Retain underlying
oracle failure status; never fabricate a successful result on an error path.

All positive correctness fixtures must have accepted EF, certified A0, objective
agreement, valid final gap/violation and complete feasible incumbent recourse.
Negative tests assert failure, not EF=A0 success. Include existing N3 mechanism
cases, explicit equal-worst ties and a multi-round scenario-addition hand case.
Rerun all N2/N3 tests without altering frozen source or historical evidence.

Evidence binds execution commit/tree, source hashes, protocol hash, environment,
full fixture/data/config hash, scenario identity/order/hash, solver outcomes and
traces. A clean execution-code commit is the external anchor; later artifact
commits do not recursively hash themselves. Timings/iterations/oracle counts are
development diagnostics only, not algorithm performance claims. N5/A1, pilot and
formal experiments remain prohibited until their respective gates.
