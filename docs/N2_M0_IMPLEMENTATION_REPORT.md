# N2 M0 IMPLEMENTATION REPORT

## Scope and specification

N2 implements only the single-resource, single-period, two-stage M0 Quantity baseline
under the frozen `MODEL_SPEC_v1.md`. There is no post-event purchase, Reliability
decision, F-OPTION, inventory age, perishability, restoration, or residual value.
N0 and N1 frozen files remain unchanged. No M1/M2, generic extensive-form framework,
exact oracle, A0/A1, convergence engine, pilot, or formal experiment is implemented.

The production schema requires finite, strictly positive shortage penalty (`s > 0`),
as frozen in N0. Zero penalty (including negative zero) is a schema rejection test,
never a solvable correctness instance. Development-only labeling does not relax
this scientific domain. The external review correctly identified the previous
zero-penalty acceptance as a specification conflict; this revision corrects it
without changing the frozen N0 design or the M0 equations.

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
| zero_demand_positive_penalty | 0 | 0 | 0 | 0 | 10 | d=0, s=10; no purchase or shortage |
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

Persisted evidence is being regenerated from the corrected committed code. The
previous `31cd350` evidence is superseded and must not be treated as conforming to
the frozen penalty domain. No N3 work is authorized by this intermediate revision.

- Execution code commit: `2229791b5f6f08fe5d2b2db9f77245c6dc76f787`
- Execution code tree: `6043ca52a7d8930182e9ac629b86ba9479f657f4`
- Evidence file SHA-256: `7c6c23bf6ba30847c2cf5df0e214011b1c9c1fdbb3a0a5bda4654638831d2f4e`
- Environment: CPython 3.12.10, Pyomo 6.10.1, gurobipy/Optimizer 13.0.2,
  gurobi_direct, Threads=1, actual license available, preflight PASS.
- Local test counts below will be refreshed after evidence regeneration.
- Previous total: 155 tests, including the unchanged N0/N1 suites and twelve independent
  saved-evidence checks in `tests/test_n2_evidence.py`.

The code commit/tree is the external execution anchor. The later evidence/report
commit adds evidence, documentation and evidence-verification tests, not model code;
it is not recursively embedded in its own evidence. Each saved case's source input
hashes are rechecked against the current code, script, dependencies and fixture.

The existing frozen CI workflow automatically collects the new tests. Its hosted
solver-free job includes equation/schema and saved-evidence verification without a
license. The licensed job remains explicitly gated by licensed-runner availability;
local licensed success is reported separately, not fabricated as hosted success.

The penalty-domain fix remains under validation until refreshed evidence and tests
are complete. N3 remains prohibited until Draft PR #3 is externally approved and
merged. No N3 work has started.
