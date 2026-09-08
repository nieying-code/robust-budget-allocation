# Final A1 Engineering Promotion v1

Status: `ENGINEERING_PROMOTION_CANDIDATE`
Scientific optimization runs: `0`

## Identity and scope

- clean source base: `main@24dbdd249c4ce6f82dfbdc6565fcb157a3b18dc3`
- engineering reference only: PR #27 head
  `675759cf955788d0200e8c1f24e7e1aff13af44b`
- final algorithm identity: `A1_FINAL_NO_MEMORY_V1`
- execution sequence: Candidate Search, then Full Exact Certification
- Formal scientific design: unchanged from the design merged at the source base
- frozen E1 sample SHA-256:
  `ac617befc8fbb7510e1b64b617c7e0339ea948ca519d0d18131f3b8048c131e0`

PR #27 was inspected as a source diff. No PR #27 commit was merged or
cherry-picked. The generic mechanisms below were reimplemented as a minimal
patch on current `main`; simulation code, scientific results, and historical
algorithm behavior were not imported.

## Final algorithm contract

`A1_FINAL_NO_MEMORY_V1` performs deterministic Candidate Search. Candidate
evaluations may identify a violated scenario, but cannot establish a formal
upper bound or convergence. Only a complete finite-scenario Full Exact
Certification can set the formal upper bound and certify the result.

The final module has no inspection phase, cache, candidate injection, ranking,
statistics, or control flow based on retained state. Its result schema does not
contain `memory_hits`. Historical modules and artifacts remain in the repository
for historical reproducibility but are not imported by the final execution path.

## Numerical validation policy

Feasibility uses

`absolute_violation <= 1e-7 + 1e-12 * family_reference_scale`.

The reference scale is computed separately for:

- objective epigraph: theta and the scenario loss for that row;
- budget: budget, first-stage cost, and scenario exercise cost;
- quantity/flow: demand and the contributing Q, exercise, and shortage terms;
- fulfillment/capacity: exercised or reserved quantity and its applicable bound.

An unrelated large quantity is never included in another constraint family's
scale. Nonnegativity and binary feasibility retain their pre-promotion absolute
rules; the family-relative term is not applied to them.

## Exact-oracle fallback

The exact oracle always attempts the existing production LP formulation first,
with the frozen production solver configuration. A scaled retry is eligible only
for a numerical solve failure; infeasibility, unboundedness, iteration/time limits,
or an ordinary accepted optimum do not trigger it.

The retry is an algebraically equivalent Pyomo `ScaleModel` clone. It changes no
scientific quantity, scenario, constraint, objective, or solver option. A solved
clone is propagated back to the original model, its objective is returned to the
original scale, and the mapped solution is subjected to the original Q-F-R
accounting and the family-specific feasibility checks. An invalid mapped solution
is rejected. Candidate Search and Full Exact Certification both call this same
exact-recourse path.

## PR #27 promotion audit

| PR #27 component | Final action | Reason |
| --- | --- | --- |
| family-specific feasibility validation | PROMOTE / REIMPLEMENT | generic numerical correctness |
| scaled exact-oracle retry | PROMOTE / REIMPLEMENT | generic numerical solver robustness |
| mapped-back original-semantic validation | PROMOTE / REIMPLEMENT | certificate correctness |
| tight-budget floating residue canonicalization | PROMOTE / REIMPLEMENT | prevents a numerically negative recourse RHS without relaxing validation |
| Memory Inspection | REJECT | final A1 has no retained-state phase |
| memory cache, injection, ranking, and hit metrics | REJECT | final A1 identity excludes them |
| `A1_full` historical label and ablation logic | REJECT | superseded algorithm identity |
| Rawls24 / E1 simulation orchestration | REJECT | scientific experiment code, not generic engineering |
| Layer A and Layer B outputs and manifests | REJECT | generated scientific evidence |
| runtime and scenario-evaluation evidence | REJECT | E5 must generate independent evidence |
| historical 1000-run diagnostics | REJECT | not needed for the generic fix |

Every promoted mechanism remains reasonable as a numerical correctness measure
without reference to the scientific outcome of PR #27.

## Source changes

- `src/robust_budget_allocation/algorithms/qfr_final_a1.py`
- `src/robust_budget_allocation/algorithms/qfr_numerical_validation.py`
- `src/robust_budget_allocation/algorithms/qfr_exact_oracle.py`
- `src/robust_budget_allocation/algorithms/qfr_state.py`
- `src/robust_budget_allocation/models/qfr_support.py`
- `tests/test_final_a1_engineering.py`

The machine-readable identity and file hashes are recorded in
`docs/evidence/FINAL_A1_ENGINEERING_PROMOTION_v1.json` and
`docs/FINAL_A1_ENGINEERING_HASHES_v1.sha256`.

## Validation boundary

Allowed validation consists of unit, regression, small correctness fixtures,
solver-free suites, and licensed tiny solver fixtures. Formal E1--E5, PR #27
N=1000 replay, performance timing, and result-driven parameter changes are out of
scope and were not executed.
