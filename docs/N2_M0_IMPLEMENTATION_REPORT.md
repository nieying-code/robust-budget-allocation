# N2 M0 IMPLEMENTATION REPORT

## Scope and specification

N2 implements only the single-resource, single-period, two-stage M0 Quantity baseline
under the frozen `MODEL_SPEC_v1.md`. There is no post-event purchase, Reliability
decision, F-OPTION, inventory age, perishability, restoration, or residual value.
N0 and N1 frozen files remain unchanged. No M1/M2, generic extensive-form framework,
exact oracle, A0/A1, convergence engine, pilot, or formal experiment is implemented.

The M0 data boundary accepts nonnegative shortage penalty as explicitly requested
for N2; `s=0` is a degenerate development test, not a change to N0's positive-penalty
scientific parameter convention. All main hand cases have positive shortage penalty.
No mathematical conflict with the frozen design was found.

## Mathematical specification to code

| Frozen M0 quantity | Code |
|---|---|
| Single resource; suppliers J and ordered finite scenarios Omega | `BudgetAllocationData`, one `resource_id`, explicit ordered tuples |
| q_j >= 0, q_j <= U_j | `model.q[j]`, continuous nonnegative with supplier bounds |
| C_Q = sum_j c_j q_j | `model.C_Q` |
| R_w = sum_j rho_j0w q_j | `model.delivered[w]`; only fixed base fulfillment input |
| x_w + u_w = d_w | `model.demand_balance[w]` |
| x_w + h_w = R_w | `model.resource_balance[w]` |
| C_Q <= B | `model.cash_budget`; no penalty in this constraint |
| theta >= s u_w | `model.worst_loss[w]` |
| min C_Q + theta | `model.total_cost` |

`x/u/h/theta` are nonnegative. `h` is measured but has no holding/disposal/expiry
cost or salvage value. The model may leave budget unused; no equality forces spending.

## Implementation files

- `src/robust_budget_allocation/data/model_data.py`: immutable new schema, exact
  supplier/scenario key validation, finite/range checks, deterministic data and scenario hashes.
- `src/robust_budget_allocation/models/m0.py`: M0-only complete finite-scenario LP,
  N1 runtime integration, invariant validation, structured result and atomic result export.
- `scripts/n2_m0_correctness.py`: a one-shot hand-fixture evidence command requiring
  clean tracked source. It is not a formal runner or registry.
- `tests/test_m0_data.py`, `tests/test_m0_model.py`: schema, equation, structure,
  hand-solution, budget-property, failure-status and provenance tests.
- `tests/fixtures/n2_m0_hand_cases.json`: eleven hand-derived cases.

## Result semantics and numerical checks

Only N1 runtime `optimal` outcomes are eligible for numerical result extraction.
All other statuses retain diagnostics and provenance but return no certified objective
or quantity. Loaded solutions are checked for finite values, supplier bounds,
cash budget, both balances, nonnegativity, epigraph and objective closure. An invalid
loaded solution becomes `numerical_invalid`, never optimal.

The epigraph LP may admit multiple allocations in a non-worst scenario. The result
preserves raw q/theta/objective/x/u/h and reports the maximal-service representative
at the same q: x=min(d,R), u=d-x, h=R-x. This does not change the objective, add a
service objective, solve recourse separately, or introduce an oracle. Equal-objective
q solutions are not tie-broken; the first worst-loss scenario in the declared order
is used only as a reporting label. This does not freeze N4's canonical tie-break.

Development checks use absolute tolerance 1e-7 and relative tolerance 1e-9. These
are N2 toy-instance checks, not the N4 E1 correctness or convergence protocol.
Minor accepted bound roundoff is retained in raw values and bounded in reported q.

## Development fixtures and hand-derived expected values

All entries are `development/correctness_evidence`; no seeds, legacy parameters,
pilot configuration or formal scientific results are used.

| Case | Optimal q | C_Q | Worst shortage loss | Objective | Unused budget | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| low_demand_full_service | 3 | 6 | 0 | 6 | 14 | Buy only demand; full service |
| budget_shortage | 2 | 4 | 30 | 34 | 0 | Three units short |
| reduced_fulfillment | 2 | 4 | 40 | 44 | 0 | Same q, fulfillment 0.5, four units short |
| supplier_price_fulfillment | (0,4) | 8 | 0 | 8 | 2 | Effective delivered unit cost favors reliable supplier |
| procurement_cap | 2 | 2 | 30 | 32 | 8 | U=2 binds |
| purchase_not_economical | 0 | 0 | 50 | 50 | 100 | c=12 exceeds s=10, buying is not economical |
| unused_resource | 6 | 6 | 0 | 6 | 4 | Low-demand scenario h=4 |
| nonworst_allocation_slack | 8 | 8 | 20 | 28 | 0 | Full-delivery scenario h=2; impaired scenario u=2 |
| zero_budget | 0 | 0 | 30 | 30 | 0 | No spending possible |
| zero_penalty_boundary | 0 | 0 | 0 | 0 | 10 | Degenerate development boundary only |
| zero_price_boundary | 2 | 0 | 10 | 10 | 0 | Free procurement still respects U=2 |

For one supplier, positive marginal loss reduction exceeds purchase cost until demand,
budget or U binds in the first five relevant cases. The uneconomical case reverses
that inequality. The two-supplier case has delivered unit costs 1/0.25=4 versus 2/1=2.
These arguments establish expected optima independently of the implementation.

## Audit evidence and acceptance

Every solve result includes input data/config hashes, ordered scenario identity,
N1 environment report, real solver version/status, Git commit/tree, current source
file hashes and dirty-source indicators. Unit-test worktree runs are honestly marked;
the persisted hand-case evidence is generated only from a clean committed source.
The evidence command scopes the N1 untracked-input gate to the actual package,
tests, scripts and configs; editable-install `src/*.egg-info` metadata is not a
scientific input. This leaves the frozen N1 validator unchanged.

The evidence JSON and final test totals are recorded after the implementation commit.
Its code commit/tree is the external execution anchor; the later evidence/report commit
adds documentation only and is not recursively embedded in its own evidence.

N3 remains prohibited until Draft PR #3 is externally approved and merged.
