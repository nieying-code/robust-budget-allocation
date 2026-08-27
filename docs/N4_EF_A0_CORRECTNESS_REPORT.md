# N4 Extensive Form + Standard C&CG correctness report

## Scope and pre-result freeze

N4 implements the complete finite-scenario M2 EF, exact fixed-decision scenario
evaluation and A0 Standard C&CG. This is development/correctness evidence only,
not formal scientific results or an algorithm performance experiment. There is
no A1, memory, candidate search, pilot or formal runner.

Base: merged N3 commit `1944dbd185dac5cb2864c1b0ad5e5dc5e52ef1c9`.
N0/N1 frozen files, N2/N3 production models/data, tests, fixtures, reports and
historical evidence/hash inventories are unchanged. N4 is entirely additive.

The protocol was committed independently before implementation or N4 results:

- Protocol: `docs/N4_CORRECTNESS_PROTOCOL.md`
- Freeze commit: `868f482a741ce34cf87050e06ffa40232a88e4de`
- SHA-256: `f3c4d4ee2d352b4b5666cfb505a6fd5d61f0d2cdff7a15ab6c6a1f0a2ec0a72f`

For a,b the acceptance threshold is 1e-7+1e-9*max(1,abs(a),abs(b)). Objective
agreement, global gap, current maximum violation and loaded feasibility checks
use this frozen rule. The protocol was not changed after results were observed.
No first-stage secondary objective or new scientific mechanism is introduced.

## Implementation and mathematical mapping

| File / interface | Mathematical role |
|---|---|
| `algorithms/extensive_form.py: build_extensive_form` | Calls the frozen N3 `build_m2` on all Omega without changing equations |
| `algorithms/common.py: build_master` | Calls that same builder on a validated nonempty subset of scenarios |
| `algorithms/exact_oracle.py: evaluate_scenario` | Calls the same builder on one scenario, fixes all q/z/y and minimizes E+s*u |
| `algorithms/exact_oracle.py: exact_oracle` | Solves every scenario in full Omega, no subset API; returns canonical maximum and complete proof |
| `algorithms/standard_ccg.py: solve_a0` | Restricted master -> complete oracle -> bounds/certification -> add violating scenario |
| `algorithms/verification.py: verify_pair` | Independently rechecks saved solver outcomes, full oracle accounting, bound/incumbent history and EF=A0 acceptance |

Paths above are relative to `src/robust_budget_allocation/`. The unchanged builder
supplies q_level/z/y_F, x/u/h/g, first-stage and scenario cash constraints, Option
cap and theta >= E+s*u. EF objective remains C_Q+C_R+K_F*y_F+theta.
Only the scenario index differs in the restricted master. The explicit first-stage
cash budget remains present, and shortage gives relatively complete recourse.

Every recourse LP retains physical balances and the same single lifecycle budget.
The oracle minimizes actual economic recourse, rather than using potentially
slack non-worst allocations from the EF/master. Raw LP values are retained.
Single-resource canonical recourse is independently computed and matched against
the solver optimum: purchase up to deficit/cap/remaining cash when p<s, otherwise
purchase zero. At p=s, g=0 is the minimum-purchase equivalent minimizer. Thus
normalization does not change economic loss or first-stage decisions.

## Exactness, bounds and termination

The N1 Gurobi runtime supplies cached preflight, construction and status mapping.
N4 sets MIPGap=MIPGapAbs=0 and feasibility/optimality/integrality tolerances 1e-9.
Only ok + optimal/globallyOptimal is accepted, followed by finite primal/solver
lower-bound agreement and raw model constraint validation. No fallback is used.
All four M2 spending terms remain separately recomputable; penalties never enter
cash. Only complete optimal, decision/data-bound oracle evidence can update UB.

- LB is the running maximum of accepted master solver lower bounds, not a
  potentially suboptimal master primal objective.
- Candidate UB is current first-stage cost plus full-Omega maximum optimal recourse.
- Global UB is the smallest candidate, retained with its producing iteration,
  first stage and entire oracle. Exact equal UB retains the earlier incumbent.
- Each successful master iteration performs one complete oracle. Any partial or
  failed oracle is rejected before updating UB or convergence.
- Convergence requires both global gap and the just-completed current oracle's
  maximum violation to pass. A materially crossed bound is numerical_failure.
- Nonconverged repeated worst scenarios are convergence_failure, never duplicate
  additions. Maximum iterations is a failure safeguard, never a certificate.

The structured result retains all iteration fields: active scenarios, master
status/objective/bound/eta, first stage, full oracle values, candidate/global UB,
incumbent iteration, LB, signed/reported gap, violation/thresholds, added scenario,
convergence and development timings. The returned best incumbent and final
current-master oracle are separately available and unambiguously linked.

Failure outcomes include solver_error, infeasible, unbounded, time_limit,
iteration_limit, numerical_failure, oracle_failure and convergence_failure.
Local optima/invalid/unknown states also remain non-success. Negative tests use
explicit synthetic fault injection; persisted positive evidence uses real Gurobi.

## Canonical rules and equivalent optima

Initial scenario is the smallest canonical string ID; active sets and full oracle
evaluation use ascending Unicode code-point ID order. Provenance additionally
retains the original data order/hash. The worst value is the numeric maximum;
exact ties select smallest ID. Near-equal lower values never replace the maximum.

EF/A0 first-stage vectors may differ at equivalent optima. Acceptance then checks
objective agreement and complete recourse/feasibility of each vector independently,
not arbitrary vector equality or matching worst IDs across different vectors.
Unambiguous cases additionally compare q, Reliability, Option and worst loss.

## Development fixtures

`tests/fixtures/n4_correctness.json` contains 15 M2 cases: the 13 N3 mechanism
input objects (now all evaluated as M2), plus two explicit N4 hand cases. N3
expected M1 objectives are not incorrectly reused as M2 expectations.

Coverage: single/multiple scenarios; Reliability no-value/value/expensive and
supplier-specific finite levels; Option on/off; unexercised scenario; contract cap;
remaining cash; expensive emergency; unused budget/resource; joint accounting.

The extra `equal_worst_canonical_id` case supplies reversed input IDs zeta/alpha,
both with loss 50, and must select alpha. `three_round_cross_failures` starts with
low demand and then exposes failure of each of two different suppliers. Its hand
optimum is q_first=q_second=4, cost 8; Option is unaffordable. A0 needs three rounds.
The initial candidate UB is 42 and the next is 44, so the trace must retain 42 and
the first incumbent until the final UB=LB=8. This also tests historical-UB binding.

All fixtures are development-only, not selected N7 parameters or scientific claims.
Runtime, iterations and oracle counts are diagnostics; no speed comparison is made.

## Evidence and tests

`scripts/n4_ef_a0_correctness.py` requires a clean committed source, tracked inputs,
no untracked scientific inputs, and unchanged commit/tree over execution. It writes
`docs/evidence/N4_EF_A0_CORRECTNESS.json` atomically, refusing to overwrite evidence.
Every EF/A0 record binds source commit/tree/hash inventory, environment, full data,
scenario ordering/hash, solver configuration/status and the frozen protocol hash.
Execution code commit/tree is the external anchor; later artifact commits do not
recursively identify themselves as their generating code.

Clean-source execution completed with all 15 comparisons PASS:

| Development case | EF objective | A0 objective | A0 iterations / complete oracle calls |
|---|---:|---:|---:|
| reliability_no_value | 4 | 4 | 1 / 1 |
| reliability_value | 6 | 6 | 1 / 1 |
| reliability_too_expensive | 8 | 8 | 1 / 1 |
| option_no_value | 4 | 4 | 1 / 1 |
| option_value | 5 | 5 | 1 / 1 |
| option_unexercised_scenario | 5 | 5 | 1 / 1 |
| option_cap_binding | 24 | 24 | 1 / 1 |
| remaining_budget_binding | 24 | 24 | 1 / 1 |
| expensive_emergency_no_exercise | 31 | 31 | 2 / 2 |
| unused_resource | 6 | 6 | 1 / 1 |
| joint_reliability_option_accounting | 8 | 8 | 1 / 1 |
| arbitrary_four_levels | 5.8 | 5.8 | 1 / 1 |
| heterogeneous_supplier_levels | 4 | 4 | 1 / 1 |
| three_round_cross_failures | 8 | 8 | 3 / 3 |
| equal_worst_canonical_id | 50 | 50 | 1 / 1 |

Maximum absolute objective difference: 0. Maximum relative difference: 0.
Maximum final violation: 0. Maximum final global gap: 0. Every accepted master,
EF and recourse solver outcome is ok/optimal with finite matching lower bound.
All final incumbent scenarios are feasible. A0 totals 18 iterations/full-oracle
calls and 29 individual scenario solves; each iteration has exactly |Omega|
evaluations. These are diagnostics, not speed/performance claims.

- Execution commit: `7da19f3f3eb53c3810f03370026add16342e7071`
- Execution tree: `0414be523d6a2157e2165c50e921d33682fa36a5`
- Evidence SHA-256: `5f29bd079a15669f6a08d9924503cc0b5adc5c1c1657f1c31a19809295c21596`
- Fixture SHA-256: `dce2c8a40ddc35486880b3915e3bfc667d40e1077e4711badc5095cbd780cc92`
- Environment: Python 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2,
  gurobi_direct, Threads=1. Real licensed preflight PASS. An integration test
  verifies one real micro-solve across EF and multi-round A0.
- Test inventory: 463 tests, comprising 391 solver-free and 72 licensed tests.
  All original 380 N0–N3 tests are retained unchanged. The 83 new tests cover
  equations, status failures, bounds, repeat handling, exact scenarios, traces,
  preflight caching, saved evidence and hashes.
- Local solver-free: 391 passed, 72 deselected. Local licensed: 72 passed,
  391 deselected. Both use the final source and saved-evidence content.
- The unchanged CI workflow automatically discovers the new tests. Hosted
  solver-free checks and their exact tested SHA are available on Draft PR #5.
  Licensed CI remains explicitly gated by runner availability; a skipped remote
  job must not be described as successful. Local real-license validation is separate.

`tests/test_n4_evidence.py` validates every saved pair and original raw recourse,
source/config/protocol/data hashes and accounting without a solver. Deliberate
subset/duplicate/decision-binding/worst-ID/raw-cash/local-status/gap/incumbent
corruption is rejected. `docs/N4_CORRECTNESS_HASHES.sha256` covers the exact 13
N4 content files, excluding itself to avoid recursion. The artifact commit/tree
externally anchors the list; N0–N3 inventories are not rewritten.

No N0/N3 specification conflict is identified. No tolerance was changed in response
to results, no previous model was refactored, and no historical evidence was altered.

N5 remains gated on external review, approval and merge of Draft PR #5, plus
pre-N5 freezing of A1 scoring/candidate/memory/state-machine/Phase III rules.
No N5 implementation has started. No scientific blocker is currently identified.
