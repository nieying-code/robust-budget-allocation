# Q-F-R Availability Correctness Regression Protocol v2.1

Status: **FROZEN BEFORE FIRST REVISED-MODEL LICENSED CORRECTNESS RUN**

Scope: correctness-only regression after the Q-availability and positive-base-F-fulfillment scientific revision. This protocol does not authorize pilot, OOS, formal experiments, algorithm redesign, performance claims, or new evidence infrastructure.

## 1. Numerical and solver policy

The R3 numerical policy is explicitly reused unchanged:

`T(a,b)=1e-7+1e-9*max(1,abs(a),abs(b))`.

Licensed solves use Python 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, `gurobi_direct`, Threads=1, no fallback, MIPGap=0, MIPGapAbs=0, and FeasibilityTol/OptimalityTol/IntFeasTol=1e-9. Only `SolverStatus.ok` with `optimal` or `globallyOptimal` is accepted.

The R3 deterministic canonical-scenario, exact finite-oracle, LB/UB, gap, violation, duplicate, tie, and iteration-safety rules remain unchanged. The R4 A1 Memory/Candidate/Full Exact Certification state machine and conditional Memory decision remain unchanged.

## 2. Revised correctness identity

Every case must bind the revised schema, including complete `d[i,omega]`, `rho_Q[i,omega]`, `delta[i,omega]`, static item parameters, revised eta levels, model kind, source commit/tree, protocol identity, solver configuration, and result identity through the existing canonical hash and replay mechanisms.

Pre-revision R3/R4 evidence is retained as historical evidence and cannot pass as revised-model evidence because its data/source/protocol identities differ.

## 3. Required cases and acceptance

One deterministic heterogeneous multi-item correctness fixture must cover M0, M1, and M2, multiple scenarios, non-unit Q availability, nonzero disruption, positive flexible exercise, shortage, and fixed-budget accounting. It is marked `CORRECTNESS FIXTURE ONLY`, not a pilot parameter set.

For every model kind, independently solve EF, A0, and A1 and validate:

- accepted solver status;
- objective agreement under `T`;
- each returned first-stage strategy's complete-scenario feasibility;
- scenario-specific `a_i*rho_Q[i,omega]*Q_i` accounting;
- F fulfillment and fixed-budget feasibility;
- worst scenario/full exact oracle;
- A0 and A1 formal LB/UB and convergence;
- final maximum constraint violation;
- existing certificate and replay closure.

Multiple optimal first-stage vectors are accepted when objective, feasibility, oracle, bounds, and provenance independently validate. Vector equality is not required.

## 4. Freeze and failure rules

The exact protocol bytes and source commit/tree are recorded before the first revised-model licensed comparison. The first run is retained whether it passes or fails. Tolerance, solver settings, fixture, scenario set, model, or algorithm may not be changed in response to results merely to obtain a pass.

A failure is classified as revised-model implementation, EF/A0/A1 adaptation, protocol implementation, solver/numerical, or newly discovered scientific blocker. Ordinary implementation defects remain in the same Draft PR; a scientific blocker stops for researcher decision.
