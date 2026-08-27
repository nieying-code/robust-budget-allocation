# N3 M1/M2 IMPLEMENTATION REPORT

## Scope and frozen baseline

N3 implements only M1 (Quantity + supplier Reliability) and M2 (M1 + F-OPTION),
under the merged N0 mathematical specification. All instances have one resource,
one period, two stages, finite ordered scenarios and no perishability or recovery.
Parameters in this stage are development/test fixtures, never N7 scientific
parameters, pilot configurations or N8 results. No formal registry is created.

Base commit: `4f3c4e96c7d16a3049da0751a2736f2597d874ae` (merged N2 PR #3).
The N2 M0 builder, production schema, eleven input fixtures and saved N2 evidence
are unchanged. N0/N1 frozen files and the CI workflow are unchanged. M0's strictly
positive shortage-penalty domain is inherited without relaxation.

Only the historical N2 evidence *test* inventory is adjusted: it now names the
exact frozen N2 source set rather than discovering every future added module.
All original N2 source SHA checks and mathematical assertions remain active.
This permits additive N3 code without retrospectively changing N2 evidence.

## Mathematical mapping and accounting

| Frozen definition | N3 code |
|---|---|
| Arbitrary finite ordered K_j, base level 0 | `ReliabilityData.levels[j]`; string `"0"` is first, other identifiers arbitrary |
| One supplier-level choice | binary `z[j,k]`, `one_level[j]` sums to one |
| Quantity split avoids products q*z | nonnegative `q_level[j,k] <= U_j z[j,k]` |
| C_Q = sum c_j q_jk | `C_Q`; q_j is reconstructed by summing levels |
| C_R = sum a_jk z_jk + pi_jk q_jk | `C_R`; fixed and unit *incremental* premiums, each charged once |
| Regular delivery = sum rho_jkw q_jk | `delivered[w]` |
| x_w + u_w = d_w | `demand_balance[w]` |
| M1 x_w + h_w = delivered_w | M1 `resource_balance[w]` |
| M1 cash <= B; theta >= s*u | `cash_budget`, `worst_loss[w]` |
| Binary Option, paid before observation | M2 `y_F`; `option_fee = K_F*y_F` |
| E_w = p_w*g_w, E_w <= F_bar*y_F | M2 `E[w]`, `option_cap[w]` |
| M2 x_w+h_w = delivered_w+g_w | M2 `resource_balance[w]` |
| C_Q+C_R+fee+E_w <= B | M2 `scenario_budget[w]`; also explicit first-stage cash constraint |
| M2 theta >= E_w+s*u_w | M2 `worst_loss[w]` |
| T-COST | `total_cost = first_stage_cost + theta` |

No shortage penalty appears in a cash constraint. Emergency expenditure appears
once in scenario economic loss and once in the separate cash feasibility check;
it is not charged again in the objective's first-stage term. Option cap is a
contract limit, not funding. There is no second budget or alternative purchase
channel. Unused budget is B minus actual scenario spending. Unused resource h has
no holding, expiry, disposal or salvage term.

Base premiums are exactly zero. Fixed and unit premiums are each finite,
nonnegative and weakly increasing with level; fulfillment is finite in [0,1] and
weakly increasing in every scenario. Base fulfillment must exactly match the
shared M0 data. K_F, F_bar, emergency price and shortage penalty must be finite
and strictly positive. Complete keys, unique ordered identifiers and immutable
copies are validated by the production schema, including for development inputs.

## Files and interfaces

- `src/robust_budget_allocation/data/mechanism_data.py`: `ReliabilityData` wraps
  frozen `BudgetAllocationData`; `OptionData` wraps Reliability. Exact JSON
  serialization and full-data SHA are provided. The common scenario SHA identifies
  the ordered base scenarios; level fulfillment/prices are additionally covered
  by the full-data SHA, not omitted from provenance.
- `src/robust_budget_allocation/models/m1.py`: M1 builder and solve interface;
  optional explicit fixed Reliability restriction supports degeneration tests.
- `src/robust_budget_allocation/models/m2.py`: M2 builder and solve interface;
  `fixed_option=0` supports the second nesting test.
- `src/robust_budget_allocation/models/mechanism_support.py`: shared N3 structured
  results, independent accounting validation and N1 runtime/audit integration.
- `tests/test_n3_schema.py`, `tests/test_n3_models.py`: schema, structure, failure,
  mechanism, repeated-solve and degeneration tests.
- `tests/test_n3_evidence.py`: independent saved-result accounting, source/hash
  verification, nesting, and comparison against original N2 scenario results.
- `tests/fixtures/n3_mechanisms.json`: thirteen hand-verifiable development cases.
- `scripts/n3_mechanism_correctness.py`: one-shot clean-source evidence generation.

The result contains objective, C_Q, C_R, total q and per-level q, Reliability
choice, Option choice/fee, delivered/x/u/h/g/E, worst scenario/loss, scenario
unused budget, raw solution, status, diagnostics and audit. M1 reports zero
Option and emergency fields for common accounting; its model has no such variables.

## Runtime and representative solutions

N1 cached preflight verifies the exact environment and real license before solving.
Only gurobi_direct with Threads=1 is used; there is no fallback. N3 integer
correctness solves set MIPGap=MIPGapAbs=0 through the N1 solver constructor.
This is an N3 execution setting, not a premature N4 E1 acceptance freeze.
Preflight is outside measured solve time and its micro-solve is process-cached.
Only N1-normalized optimal status permits extraction; local optima, conflicts,
limits and invalid statuses do not become certified solutions.

Extraction validates finite values, all raw bounds, binary integrality, fixed
decisions, every raw constraint and independently reconstructed costs, cap,
scenario cash and objective. Invalid solutions return `numerical_invalid`.
Development checks retain N2 absolute 1e-7 / relative 1e-9 tolerances; these are
not the future N4 convergence or correctness acceptance protocol.

As in M0, non-worst scenarios can have allocation slack. Reported x/u/h select
maximal service at unchanged q/z/y/g, and raw values are retained. This does not
change the objective or add a service objective. Non-worst emergency g may also
be nonunique; it is retained, not separately reoptimized. First-stage ties are
not newly tie-broken. The first worst scenario in declared order is a reporting
label, not N4's still-to-be-frozen canonical tie-break. No exact oracle is added.

## Hand fixtures and expected results

| Case | Expected result | Economic / physical check |
|---|---|---|
| reliability_no_value | base, q=4, objective=4 | Same fulfillment cannot justify positive premium |
| reliability_value | level 1, q=4, C_R=2, objective=6 | Base needs q=8 at cost 8 |
| reliability_too_expensive | base, q=8, objective=8 | Added fixed/unit fees outweigh quantity saving |
| option_no_value | y=0, q=4, objective=4 | Regular unit cost 1 beats fee plus price 2 |
| option_value | y=1, q=0, g=4, E=4, objective=5 | Fee 1 plus emergency 4 beats regular cost 16 |
| option_unexercised_scenario | y=1, g_low=0, g_high=4, objective=5 | No order in zero-demand, expensive scenario |
| option_cap_binding | y=1, E=3=cap, u=2, objective=24 | Fee 1 + exercise 3 + shortage loss 20 |
| remaining_budget_binding | y=1, E=3, B=4, objective=24 | Cap 100 adds no funding; remaining cash binds |
| expensive_emergency_no_exercise | y=1, g_expensive=0, objective=31 | Price 20 exceeds s=10; cheap scenario makes option worthwhile |
| unused_resource | y=0, q=6, h_low=4, objective=6 | Budget cannot afford fee 20; low demand leaves stock |
| joint_reliability_option_accounting | level 1, y=1, q=2, g=2, objective=8 | C_Q=2, C_R=1, fee=1, E=4; remaining cash=2 |
| arbitrary_four_levels | gold, q=4, C_R=1.8, objective=5.8 | Enumerated levels have costs 15, 7.1, 5.8, 5.9 |
| heterogeneous_supplier_levels | base, q=(4,0), objective=4 | Supplier-specific level counts supported |

All cases use positive s. Four levels and heterogeneous sets demonstrate that no
official two/three-level decision has been made. Fixtures do not select formal
parameters or scientific conclusions. In the expensive-price case, cheap-scenario
g can vary without changing worst loss; only the economically forced expensive-
scenario non-exercise is asserted.

## Strict nesting and M0 regression

Fixing M1 z_j0=1 eliminates every nonbase q through the link constraints. Base
premium is zero and base rho matches M0; the resulting equations are exactly M0.
Fixing M2 y_F=0 gives E=0 and, since every p is strictly positive, g=0. The remaining
constraints and objective are exactly M1. These are algebraic identities.

For each of thirteen identical full input cases, automated real-solver tests compare
M1(base) versus M0: objective, C_Q, q, x/u/h, worst loss and worst scenario; and
M2(off) versus M1: those fields plus C_R, per-level q, Reliability choice and unused
budget. Every off-case also checks all g/E=0. All share the same base data and
ordered scenarios. Equality of solver-selected decision vectors is demonstrated
on these fixtures; arbitrary tied optima need not return identical solver choices.

The original eleven M0 hand cases are also rerun unchanged. Existing N2 tests,
including historical evidence/source hash checks, remain part of the full suite.

## Evidence, tests and review gate

Persisted evidence is `docs/evidence/N3_M1_M2_CORRECTNESS.json`. Its generation
requires clean tracked source and no untracked scientific inputs, and checks that
commit/tree do not change during execution. Every result binds code commit/tree,
source file SHA, full data/config SHA, environment, solver version and actual status.
The code execution commit/tree is the external anchor; the later evidence/report
commit does not recursively hash itself. No formal experiment outputs are created.

Persisted execution: 71 optimal solve records; 13 mechanism cases, 13 paired
degeneration cases and 11 M0 regression cases all PASS.

- Execution code commit: `ec624e38b4ebf06d20f605671017e7baa19b883c`
- Execution code tree: `bc34a776b74dbcf050e49cf791b0a29c9dc05e26`
- Evidence file SHA-256: `17b61f8db6663d54b706101c4109b522f303046f2b6925553cbf2da412057e48`
- Fixture file SHA-256: `9db4fb519c72dc155260c1c5c5b64fd4e1b619adc821dab5c82733ebcd312b8c`
- Environment: CPython 3.12.10, Pyomo 6.10.1, gurobipy/Optimizer 13.0.2,
  gurobi_direct, Threads=1; real license available; preflight PASS.
- Test inventory: 380 tests, including 331 solver-free and 49 real licensed tests;
  110 saved N3 evidence/inventory checks are included in the solver-free group.
- Local solver-free: 331 passed, 49 deselected. Local licensed: 49 passed,
  331 deselected. See Draft PR #4 checks for the exact CI-tested SHA.
  Hosted licensed CI remains explicitly gated and must not be
  reported as passed when it is skipped; local real-license evidence is separate.

`docs/N3_M1_M2_HASHES.sha256` covers the exact twelve N3 new/modified content files
(including the inventory test and this report). The list excludes itself to avoid
recursive hashing; Git commit/tree externally anchor both the list and all content.
The test rejects missing/duplicate/absolute/traversal paths and missing/non-file or
hash-mismatching entries. Neither N0 nor N1 hash inventories are rewritten.

No N0 specification conflict or scientific-model blocker has been identified.
N4 entry still requires external review, approval and merge of Draft PR #4 and
the pre-N4 E1 standards freeze. No N4 generic EF framework, oracle, A0/A1, candidate
search, memory, convergence engine, pilot or formal experiment is implemented.
