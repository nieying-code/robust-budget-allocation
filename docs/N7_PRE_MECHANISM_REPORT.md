# N7-pre Option–Memory mechanism confirmation — Layer 1 stop

N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

## Final scientific and execution states

**N7_PRE_OPTION_GATE_FAILED**  
**N7_PRE_MEMORY_NOT_IDENTIFIED**

Layer 1: 18/18 configurations, 90/90 method runs success/certified. All 18 paired
EF/A0/A1 checks pass. Each preregistered F-favored economic-condition cell has
0/6 EFFECTIVE_OPTION_ACTIVE. Layer 2 was NOT executed: 36 frozen configs remain
unrun. Execution/replay PASS is not a scientific Gate M PASS. No parameter
changes, new seeds, retries, additional configurations, Memory deletion, formal
N7/N8 execution or automatic merge occurred.

## Governance and bounded engineering repair

N6 formally closed by user confirmation after PR #8 merged at
17994d9467cb265e032b5aee1b5dc843b9ae3f7c, 2026-08-28T07:46:00Z.
Branch: n7-pre/option-memory-confirmation.
Draft PR #9: https://github.com/nieying-code/robust-budget-allocation/pull/9.
Earlier premature PR #7 merge history and all N0–N6 files remain unchanged.

The original prelaunch attempt 21e217a974e82027364494b2a2342562786ed526
(tree f577262b7838976878c28dffe7e6a244a03dabba) stopped before gates/tests/science.
Its failure JSON and authenticated source archive remain immutable under
docs/evidence/N7_PRE_ENTRY_*. The user independently confirmed the root cause and
explicitly authorized bounded repair with conditional automatic relaunch.

Only production change: mechanism_confirmation/audit.py scans the actual
src/robust_budget_allocation/ package rather than its src/ parent. The five
ignored sibling egg-info metadata files remain intact. tests/scripts/configs,
required tracked files, source cleanliness, native Git proof, inventory/hash,
canonical serialization and replay checks remain. N1 validator is unchanged.
No model/algorithm/protocol/matrix/seed/tolerance changes were made.

Repair and sole scientific execution commit:
172b63716fa023d8fbb83193b2e4a06dba543eaf.
Execution tree: fda896563268e97ed2e3e7492dd790a8d3852adf.
Working tree was clean at both gates and scientific launch. Every run binds this
same source; subsequent delivery commits only add/update tests, reports and audit
artifacts. No production code was changed after science began.

## Registration and prelaunch evidence

Registration commit: 4df5d90c8a3bd5a131cd47f8f7baba55e90773ac. ALL54 configs and
six seeds were frozen before any results. Seeds remain:
4289336819, 2954552515, 414623883, 2596770366, 799209694, 304170811.

| Frozen item | SHA256 |
| --- | --- |
| Protocol | b110e1ecf24b83c2fa217204bb35177be72cc13da57ef7e8d7b81d14b1497b1e |
| Matrix | b25eea24b3610c0635262fae2549958d16058ff7a3f2aad8ae31fe44a9d10d16 |
| Seed registry | 5af50e8c337691652bd9045e4957c5fc61778aa096778fcedf0ba8791dd8e71b |

Initial repair validation: 721 solver-free tests PASS, including 13 real
production-entry integration tests in genuine depth-one clones/subprocesses.
Coverage: sibling metadata acceptance; ignored AND untracked pollution in all
four protected directories rejected; missing required files and tracked
tampering rejected; real persisted JSON -> production validator passes and
forged full source content fails. No validator monkeypatch or full-history
dependency. Synthetic gate fixtures are explicitly engineering tests, not license
evidence. Existing Windows high-frequency heartbeat/read-replace and process-tree
tests, historical shallow replay and forged-trace protections also pass.

Independent repair-validation directory:
outputs/harness-validation/n7-pre-repair-v1/. Frozen inputs/source/delivery checks
passed (19/19 then-current hashes); scientific counter=0, no batch existed.

Complete production prelaunch at outputs/harness-validation/n7-pre-v1/:
721 solver-free tests PASS; 100 real licensed tests PASS; no skips in either local
suite. Actual environment: CPython3.12.10, Pyomo6.10.1, gurobipy13.0.2,
Optimizer13.0.2, gurobi_direct, Threads1, license available, preflight PASS.
Production gate JSON was written, reread and fully validated. No scientific
worker started before all gates passed. The 3 pytest warnings only concern
record_property/JUnit xunit2 formatting in existing Windows stress tests.

## OBSERVED — Option gate and model accounting

| Preregistered economic-condition cell | Completed seeds | EFFECTIVE_OPTION_ACTIVE |
| --- | ---: | --- |
| F-favored x B45 | 6/6 | 0/6 |
| F-favored x B90 | 6/6 | 0/6 |
| F-favored x B150 | 6/6 | 0/6 |
| Reference x B45 | 0/6 | NOT RUN |
| Reference x B90 | 0/6 | NOT RUN |
| Reference x B150 | 0/6 | NOT RUN |
| Balanced x B45 | 0/6 | NOT RUN |
| Balanced x B90 | 0/6 | NOT RUN |
| Balanced x B150 | 0/6 | NOT RUN |

Each of the 18 completed configs has purchase=false, no exercise scenarios,
and no objective improvement beyond the frozen numerical-equivalence tolerance.
All final M2 decisions have y_F=0 and all g/E values zero. Maximum absolute
M1–M2 objective discrepancy is 4.547473508864641e-13 (numerical noise, not value).
The full-precision per-seed booleans, differences and tolerances are in
N7_PRE_DIAGNOSTIC_SUMMARY.json, not inferred from rounded report values.

M1 selects paid Reliability in 14/18 configs; M0 and M1 are equivalent in the
other four. At B45/B90/B150, observed M2 total Quantity ranges are respectively
32.137–45.000 / 64.764–82.445 / 105.304–113.268. These are descriptive allocation
patterns only, not causal budget effects or substitution/complementarity claims.
Sixteen M2 first-stage budgets bind within tolerance. Two B150 cases (seeds
2954552515 and 304170811) leave approximately9.4914 and13.7919 unused cash and
meet all scenario demands without Option. Unused cash is not Flexibility.

Read-only production replay passes all90 runs. max|Z_A0-Z_A1|=0;
maximum EF/A0/A1 spread=2.2737367544323206e-13. Separate arithmetic tests recompute
all1080 run-scenario rows: Quantity/premium/fee costs, emergency spending,
same-B cash, demand/resource balances, shortage/h and worst-loss objective.
No penalty enters cash and no expenditure is counted twice. All source,
data/config/scenario, trace/output and file inventories are retained.

## INFERRED — bounded structural/economic diagnosis

The preregistered existence test did not establish genuine Option value in ANY
of the three tested F-favored cells across the six seeds. This is a scientific
warning requiring independent structural/economic review, not an execution
failure and not permission to continue Layer 2 or tune until activation.

'F-favored' is a registered relative-cost label, not a mathematical guarantee of
Option optimality. Even with the authorized premium multiplier1.5, paid regular
variable costs are1.27/1.48/1.725 per ordered unit, plus fixed premiums3/3.75/4.5.
Paid fulfillment follows rho1=.65+.35*rho0. Option still costs a positive fee4
and 1.8–3.2 per exercised unit within the same B, with spending cap45. This makes
regular Quantity/Reliability economically competitive and leaves a real
cross-stage funding trade-off. These accounting relationships are a plausible
explanation, **not a proof of global dominance or an identified causal effect**.

The observations rule out a claim of demonstrated Option benefit in this bounded
study. They do not isolate whether the absence is caused by candidate coverage,
the fulfillment-improvement structure, joint relative economics, finite scenario
sampling or their interaction. No constrained-Option solve, new calibration,
additional seed or counterfactual scientific run was performed. Those would
require a new explicit scientific decision; no specific revised values are
proposed here.

## OBSERVED — algorithm diagnostic and runtime

| Metric, total over18 paired runs | A0 | A1 |
| --- | ---: | ---: |
| Iterations | 60 | 60 |
| Scenarios added | 42 | 42 |
| Full exact / complete oracle calls | 60 / 60 | 18 / 18 |
| Scenario evaluations | 720 | 276 |
| Phase I hits | n/a | 0 |
| Phase II hits | n/a | 42 |
| Phase III calls | n/a | 18 |
| Per-run iterations / final active-set range | 1–6 / 1–6 | 1–6 / 1–6 |
| Algorithm median seconds | 0.258379 | 0.128075 |
| Algorithm min–max seconds | 0.087128–0.520658 | 0.094214–0.186088 |

Timers preserve the frozen common boundary; preflight/construction and
serialization are separate. Supervisor wall-time sum over all90 methods is
195.714640 seconds, not the same as algorithm time. These are measured diagnostic
workloads, not runtime-superiority or formal scaling conclusions.

A1 has60 master states, all y_F=0. Full oracle occurs only at the terminal
iteration of each run. Memory first populates at iteration1 in every run; there
are25 later nonterminal iterations but no eligible stored nonactive scenario
in any Phase I ranking. Actual MEMORY_OPPORTUNITIES=0, not25. Relevant
Option-active A1 trajectories=0. Memory is NOT IDENTIFIED, not judged ineffective
and not removed. See N7_PRE_MEMORY_DIAGNOSIS.md for the opportunity logic.

## NOT ESTABLISHED and warnings

No universal dead-mechanism theorem, Risk/Budget causal effect or threshold,
activation probability, single-cost-parameter effect, formal statistical
significance, Q/R/F substitution/complementarity or runtime superiority is claimed.
Option-active algorithm behavior and Memory contribution remain unobserved.
Candidate workload evidence here occurs with Option off; it cannot establish
performance with Option active. No formal scenario scale or N7/N8 matrix is set.

One post-run ad-hoc summary extraction initially referenced a nonexistent
supervised_seconds field; the actual retained watchdog field is wall_seconds.
The extraction was corrected without rerunning any solve or modifying raw
evidence. This was not a production execution, replay or source-integrity failure.
Both raw archive copies remain byte-identical.

## Delivery and stop

N7_PRE_DIAGNOSTIC_EVIDENCE.json.gz is the byte-identical compact raw90-run archive,
SHA256 1a4e38b21c0e9b89d2c4d58e3a61fdd3f1c53ac416a43c0abbeef86915ce2ade.
It embeds the actual execution Git objects AND real prelaunch suite XML/proofs;
read-only replay does not require local execution history or a solver license:

    python scripts/n7_pre.py replay --evidence docs/evidence/N7_PRE_DIAGNOSTIC_EVIDENCE.json.gz

Repair validation, execution manifest, derived full-precision summary and replay
receipt accompany it. Original per-run directories stay under
outputs/n7_pre/n7pre01/. Old entry failure and all N6 evidence are preserved.
N7_PRE_DELIVERY_MANIFEST.json / N7_PRE_HASHES.sha256 provide the exact updated
inventory; the hash list excludes itself and delivery commit/tree are external
anchors. Post-delivery tests add independent accounting and true shallow CLI
positive/forged-proof cases; no licensed/scientific rerun is needed.

Final local delivery regression on commit9855ce8cf337a479dfa02336b6b6a58f815cc140:
**730 passed, 100 licensed deselected**, 383.11s; only the same3 existing JUnit
format warnings. Includes genuine depth-one90-run CLI replay without execution
history/license and four rejection cases (missing object, tampered object,
incomplete source inventory, forged diagnostic gate). Independent1080-row
accounting and25/25 delivery hashes PASS. The later report-only QA commit does
not change execution code, scientific inputs or raw evidence. PR CI remains the
current delivery-commit regression record, not scientific Gate M approval.

STOP for independent scientific review. PR #9 remains Draft/OPEN; no merge,
Layer 2, automatic parameter repair, final algorithm change or formal N7/N8.
