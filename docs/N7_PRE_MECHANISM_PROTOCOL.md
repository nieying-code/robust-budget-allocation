# N7-pre Option–Memory mechanism confirmation — pre-result freeze

N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

## Governance and independent preregistration

User explicitly confirmed N6 formally closed and authorized N7-pre after PR #8
merged. Verified merge/base: 17994d9467cb265e032b5aee1b5dc843b9ae3f7c,
2026-08-28T07:46:00Z. Begin from that clean base on a new branch and new Draft PR.
The earlier PR #7 premature-merge event remains unchanged history, not authority.
Do not modify/overwrite/reinterpret any N6 evidence. No automatic merge or N7
formal/N8 work. This protocol, matrix.json and seeds.json are committed together
before implementation results or any N7-pre scientific solve; no results are known.

## Scope and fixed 54-config registration

Goal M: existence of reproducible genuine Option value in a preregistered economic
condition. Goal A: lightweight Memory opportunity/hit diagnosis, not the primary
gate. No causal risk/budget/single-parameter effect, threshold, substitution/
complementarity, activation probability, significance or runtime superiority claim.

configs/n7_pre/matrix.json registers ALL 54 configs: 3 regimes x 3 budgets x 6 seeds.
An economic-condition cell is regime x budget, with six seeds. All 54 are frozen
now, including conditional Layer 2. Order: F-favored, reference, Balanced; within
each, B45, B90, B150; within each budget, seed indices1..6. Methods per config:
M0, M1, M2-as-EF, then A0/A1 in even-index order and A1/A0 in odd-index order
(zero-based global config index). Thus Layer1=18 configs/90 method runs, Layer2
=36 configs/180 runs, maximum54 configs/270 runs. Never splice old results.

| Regime | Paid fixed AND unit premium multiplier | K_F | Emergency price |
| --- | ---: | ---: | --- |
| N6 reference / R-favored | 1.00 | 6 | 2.2+1.8v |
| Balanced | 1.25 | 5 | 2.0+1.6v |
| F-favored | 1.50 | 4 | 1.8+1.4v |

These are economic-condition bundles, not single-factor causal interventions.
Advance costs1/1.15/1.35 remain below every emergency price; all emergency prices
are below shortage penalty8. Positive fees and a same-B cap preserve trade-offs.
Risk0.40 is controlled in every config, not evidence of absent risk effects.

## Seeds and invariant generation

Six diagnostic seeds in frozen registry order:
4289336819, 2954552515, 414623883, 2596770366, 799209694, 304170811.
Rule: unsigned integer from the first8 hex characters of SHA256 of UTF8
robust-budget-allocation/N7-pre/diagnostic/v1/ followed by index1..6.
They are distinct from61001/61002. No existing formal/OOS seed registry is frozen
at this base; these six are explicitly excluded from all future formal/validation/
OOS seed allocations. No seventh seed, replacement, discarded unfavorable seed
or outcome-dependent new config. Separate PRNG streams; no population inference.

Keep N6 main-size12 scenarios (not its24-scenario capacity probes), one commodity,
three suppliers j0/j1/j2, levels0/1. Costs(1,1.15,1.35), caps(60,50,40), penalty8,
base premiums0, paid fixed(2,2.5,3), paid unit(.18,.22,.25), Option spending cap45.
Each regime multiplier applies uniformly to both paid premium vectors.
No supplier-specific tuning. Fixed total budget/T-COST and all models unchanged.

For each config use a fresh random.Random(seed) on CPython3.12.10. For w000..w011:
one demand variate, then each supplier's risk-state and severity variates, then
one emergency-price variate. demand=round(60+40v,8). If state<0.40,
rho0=round(.10+.30severity,8), else round(.85+.15severity,8).
rho1=round(rho0+.65*(1-rho0),8). Price=round(regime_intercept+regime_slope*v,8).
This exactly preserves N6's demand/fulfillment/generation structure and RNG
consumption, changing only authorized economics and seeds. Use common variates
across regimes/budgets for each seed. No recovery/perishability/new financing.

## Effective Option and Gate M

Use unchanged N4 T(a,b)=1e-7+1e-9*max(1,abs(a),abs(b)). EFFECTIVE_OPTION_ACTIVE
iff M2 EF's y_F=1 AND at least one SAME scenario has g>T(g,0) and E>T(E,0)
AND Z_M1-Z_M2>T(Z_M1,Z_M2). Record all three booleans, raw differences and
tolerances, canonical scenario accounting, and EF/A0/A1 equivalence proof.
No economic/percentage/statistical threshold, and no change to solver tolerances.

Complete ALL18 Layer1 F-favored configs before computing cell counts (unless any
execution/correctness failure stops immediately). No early success stopping.
At least one F x B cell with>=3/6 effective seeds => N7_PRE_OPTION_GATE_PASSED.
Interpret only finite registered cell evidence of a non-dead Option mechanism,
not a population50% activation probability or identified threshold/effect.
Any effective config but all cells<3/6 => N7_PRE_OPTION_GATE_INCONCLUSIVE; stop.
Zero effective configs => N7_PRE_OPTION_GATE_FAILED; stop for structural/economic
diagnosis, not parameter changes. Only PASS authorizes fixed Layer2 remaining36.
No additions, fee/price reductions, premium/risk changes or retries after results.

## Memory opportunity and preregistered decisions

Preserve current A1 for ALL permitted diagnostic configs. Report each trace's
memory_before/after, first population iteration, IDs, prune reasons, ranking,
planned/evaluated IDs and hits. Verify them with frozen N5 replay, not stored
counters alone. Count one MEMORY_OPPORTUNITY per later NONTERMINAL iteration
(row.certified=false, successfully continued/added scenario) if memory_before is
nonempty and frozen post-prune Phase I ranking contains at least one eligible
stored nonactive scenario. Count iterations, not number of entries. Record IDs
and the actual inspected subset. Eligible terminal iterations are reported
separately, not silently counted. Population at final termination without a later
eligible nonterminal iteration is zero opportunity, not Memory failure.

A relevant Option-active A1 trajectory contains at least one accepted exact
scenario evaluation at a master y_F=1 with same-row g>T(g,0) AND E>T(E,0).
This includes partial or full evaluations; a merely purchased but unexercised
intermediate Option is not sufficient. Report this trajectory flag separately
from config EFFECTIVE_OPTION_ACTIVE and final incumbent purchase/exercise.
Aggregate opportunity count and Phase I hits over relevant trajectories for the
decision; also report all-run counts. No hit-rate, runtime or percentage threshold.

After permitted diagnostic execution: zero relevant opportunities =>
N7_PRE_MEMORY_NOT_IDENTIFIED, no deletion. Positive opportunities and positive
Phase I hits => N7_PRE_MEMORY_REVIEW_REQUIRED; preserve current Memory, independent
review decides structure. Positive opportunities and zero hits => remove Memory
only, Candidate Search -> Full Exact Certification, without changing candidate,
oracle, convergence or tolerances. This conditional change occurs AFTER diagnostic
collection, under a separate clean final-algorithm source anchor, never mid-batch.
Validate EF≈A0≈A1_final anew on all existing N4 correctness cases plus the completed
diagnostic cases; retain old evidence separately, then N7_PRE_MEMORY_REMOVED.
Old N5/N6 proof does not automatically certify changed code. If Gate M stops the
study, its immediate stop overrides any further scientific validation; report
the observed conditional Memory branch and await review rather than invent proof.

## Execution, correctness, failure and audit

Use Python3.12.10/Pyomo6.10.1/gurobipy and Optimizer13.0.2, gurobi_direct,
Threads1, MIPGap=MIPGapAbs0, feasibility/optimality/integrality tolerances1e-9.
Unchanged N1 status/license/preflight-once semantics and frozen N4/N5 correctness
protocols. No fallback, warm start or cross-run Memory. Same input and solver for
M0/M1/EF/A0/A1. max_iterations13 (|Omega|+1). N6 watchdogs unchanged:
startup60s, algorithm120s, postprocess60s; use bounded heartbeat conflict handling.

Before science, commit implementation and run solver-free and real licensed
regressions plus environment preflight on a clean source. All diagnostic runs
share that single execution commit/tree and complete source manifest. Check
canonical full source contents across JSON boundaries, not only digest fields.
Record preregistration commit and protocol/matrix/seed hashes. No execution code
edits during Layer1/2. A separate immutable batch ID, no continuation or overwrite.

Any solver_error, infeasible/unbounded, time/iteration limit, numerical/oracle/
verification failure, interruption, incomplete output or source mismatch stops
the batch immediately. Keep original run/partial files and error context, no retry,
seed replacement, skip or silent deletion. Correctness mismatch =>
N7_PRE_BLOCKED_BY_CORRECTNESS; do not continue scientific interpretation/layers.
Other engineering failures are reported as blockers, never coerced into Gate M.

Reuse only engineering/measurement helpers without mutating N6. New outputs under
outputs/n7_pre/, never outputs/pilot/ or outputs/formal/. New run ID, exclusive
file lease, atomic writes, immutable file inventory and normalized status. Each
record binds source commit/tree, environment, protocol/matrix/seed hashes,
config/data/scenario hashes, UTC/timing, objective/LB/UB/gap/signed gap/tolerance,
exact violation, certification, trace hash, output hash and cleanup evidence.
Preflight/construction/algorithm/master/oracle/serialization-audit timing remain
separate. Store compact evidence, full traces, hashes and authenticated Git object
proof for actual shallow-clone solver-free replay; no monkeypatched production
object store. Replay every run before continuing and every complete config with
EF/A0/A1 agreement and M2<=M1<=M0, physical and cash accounting. Recompute gates,
Memory summaries and numerical comparisons from authenticated original traces.

## Outputs, language and stopping

Deliver N7_PRE_MECHANISM_REPORT.md and N7_PRE_MEMORY_DIAGNOSIS.md, frozen matrix/
seed registry, source manifest, compact immutable evidence, replay, 9x6 cell table
(unexecuted cells explicitly NOT RUN), workload and numerical comparison evidence.
Every report separates OBSERVED, INFERRED and NOT ESTABLISHED. No causal risk/
budget effect, threshold, population activation rate, significance, substitution/
complementarity, formal sensitivity or runtime-superiority claim. Report full
warnings and any conditional algorithm-change evidence. Keep the new PR Draft,
STOP for independent review, no automatic N7 formal experiment design or N8 run.
