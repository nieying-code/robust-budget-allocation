# N6 pilot protocol — pre-result registration

PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

## Authority, scope and freeze

N0–N5 are merged; baseline commit is
9dc61f3f7d4b329a2bcf65084c56bbfc1cee78bc (merged PR #6).
Commit this protocol and configs/pilot/n6_candidates.json independently BEFORE
implementation execution or inspecting any N6 solution. No pilot has run when
this registration is made. Later execution-code and artifact commits are external
anchors, never self-hashed. This document and the registered config must remain
byte-identical. New source is an execution/diagnostic layer only. No changes to
models, schemas, solver runtime, EF/oracle/A0/A1, scoring, memory, tolerances or
N0–N5 documents are authorized. No N7 freeze, OOS study or N8 formal output.

Frozen N4 protocol SHA256:
f3c4d4ee2d352b4b5666cfb505a6fd5d61f0d2cdff7a15ab6c6a1f0a2ec0a72f
Frozen N5 protocol SHA256:
c674f64297e6ad47fca0feeb593cd31202f370a6c567d5620d7f26ccab360a12

N6 adds scientific-informativeness diagnosis as explicitly authorized in this
stage request, without changing the N0 formal scientific design or treating
diagnostic observations as scientific effect estimates.

## Fixed finite pilot matrix and candidate rationale

Exactly 16 configurations, 80 planned algorithm/model runs, 16 A0/A1 pairs
(32 paired runs). No outcome-driven additions. Twelve primary configurations:
B in {45,90,150}, disruption risk in {low,high}, seeds {61001,61002}, |Omega|=12.
Two one-factor contract contrasts: high/61001/B90/12 with either premium x2 or
Option fee x2. Two size probes: high/B90/|Omega|=24, each registered seed.
All |I|=1, |J|=3, supplier IDs j0,j1,j2, two candidate levels "0","1".
This is not a factorial formal matrix and cannot establish comprehensive effects.
No development fixture/seed is promoted; these new seeds are reserved for pilot
and must be excluded from future formal/validation/OOS seed sets.

All values are normalized illustrative currency/resource units, NOT empirical
calibration or literature claims. Unit procurement costs (1,1.15,1.35), supplier
caps (60,50,40), shortage penalty 8. Purchase of a typical demand 80 costs roughly
80–108 before protection: B45 is tight, B90 intermediate, B150 loose. Premium
base=0, paid fixed premiums (2,2.5,3) and unit premiums (.18,.22,.25), multiplied
by the registered premium factor. Paid fulfillment rho1=rho0+.65*(1-rho0).
This restores only part of failed delivery, obeys weak monotonicity, and is not
a new recovery process. Option fee 6 times registered fee factor, cap 45.
The cap is contractual spending permission, never funding; every exercise
retains the frozen same-B constraint. Fee is about six base units; cap covers
roughly 11–20 emergency units; emergency price exceeds advance cost but remains
below penalty. These relative costs allow trade-offs without guaranteeing
activation. Premium/fee doubling is a prespecified price contrast, not tuning.

## Deterministic scenario construction (pilot-only)

Use local random.Random(seed), CPython 3.12.10, no global RNG or old generator.
For each scenario in increasing index order, consume exactly:
one demand uniform variate, then for EACH supplier one risk-state variate and
one severity variate, then one emergency-price variate.
ID is w000, w001, ... . Demand=60+40*v.
Disruption if state variate < .08 (low) or .40 (high).
rho0=.10+.30*severity if disrupted, otherwise .85+.15*severity.
Emergency price=2.2+1.8*v, same rule in both regimes.
Round demand/price/rho0 to 8 decimal places; round rho1 to 8 decimals.
Risk changes only disruption threshold using common random numbers: demand and
price are identical across matched budgets/risk/contracts. Size probes extend
the identical scenario prefix. Scenarios are finite stress candidates; no
probability-weighted robust objective or fitted joint distribution is introduced.
All generated inputs must pass unchanged production schemas (s,K_F,F_bar,p>0).

## Execution, acceptance and stop rules

For each config in registered order, solve native frozen M0 and M1 builders using
the unchanged N4 exact runtime, then frozen M2 EF and paired A0/A1. Alternate
paired order by config index: even A0 then A1; odd A1 then A0. Serial runs, no
cross-run memory, fresh worker process for each run, no warm starts.
The M0/M1 adapter changes no equations and validates raw feasibility, exact solver
bound, reconstructed first-stage cost and canonical non-emergency recourse.
Native builders remain distinct, not transformed into another scientific model.

Same A0/A1 data, all-level scenario payload, options, environment and max_iterations
=|Omega|+1. Initial active ID and all tie/recourse choices follow N4/N5. Use
T(a,b)=1e-7+1e-9*max(1,abs(a),abs(b)) without relaxation. Verify EF=A0=A1 and
M2<=M1<=M0 with accounting; do not require identical arbitrary optimal decisions.
Only accepted full-oracle certification can yield A0/A1 success.

CPython 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct, Threads=1,
MIPGap=MIPGapAbs=0, FeasibilityTol=OptimalityTol=IntFeasTol=1e-9.
No solver fallback. N1 ensure_preflight_once runs before algorithm timing in each
fresh worker; cached checks inside scientific calls must not rerun license solves.
Algorithm watchdog=120s after worker signals algorithm start; startup/preflight
watchdog=60s; postprocess watchdog=60s. These are external wall-clock limits,
NOT changes to frozen solver options. Terminate the worker on deadline and retain
its partial files/logs. A killed run cannot certify; trace may be absent and must
be explicitly marked incomplete. The watchdog does not manufacture solver bounds.
No automatic retry, seed replacement, or in-place resume. Manual retry requires
external authorization, new run_id, parent_run_id and retry_reason; old artifacts
are immutable. Resume means reporting already completed runs, not rewriting them.
An abandoned started run is interrupted/incomplete, never success.
Any non-success stops the remaining matrix pending diagnosis. A correctness or
verification failure is N6_BLOCKED_BY_CORRECTNESS; preserve it and do not fix
frozen code while continuing pilots. Scientific risk is assessed after the
prespecified successful matrix, without adding configurations.

Failure taxonomy: success/certified, solver_error, infeasible, unbounded,
time_limit, iteration_limit, numerical_failure, oracle_failure,
verification_failure, interrupted, incomplete; retain underlying raw status and
diagnostic (including convergence_failure as verification_failure).
Operational fault-injection tests are development tests, not pilot successes.

## Timing, memory and storage

Record separate preflight, deterministic construction, call envelope, frozen
algorithm wall-clock, master solve, full oracle wall-clock, partial evaluation
solver time, replay/audit and serialization durations. A0/A1 principal comparison
uses their unchanged internal runtime_seconds (starts after source audit/preflight,
ends before result hashing). Wrapper envelope is separately recorded, not mixed.
Master time is sum of trace master solver runtime; full oracle wall is sum of
actual full-oracle trace times; A1 partial evaluation time is sum of actual
Phase I/II solver runtime (excludes their model-building overhead). Label this
limitation explicitly; residual algorithm time includes partial building, memory,
ranking and Python overhead. Do not pretend these are mutually exclusive with
the total. Never sum repeated incumbent certificates as additional work.
Same instrumentation for paired algorithms, no profiling or monkeypatch of frozen
algorithm code. Record Python traced peak memory over the call (same tracemalloc
boundary) and explicitly note it excludes Gurobi/native memory; process peak RSS
where available is a separate lifetime metric including startup. No parallel
throughput claim. Store raw files only under outputs/pilot/, never outputs/formal/.

## Immutable run and audit schema

Each run has unique safe run_id; refuse duplicate directories and path traversal.
Use N1 file lock and atomic I/O. Hold a supervisor lease for the whole run;
worker status/heartbeat events are atomic and stage-specific. An OS-released
stale lock file is not an active lease; an existing started run is still not
reusable. Concurrent acquisition fails fast. Partial JSON or missing terminal
record is incomplete, not silently ignored. Record stdout/stderr for failures.

Run metadata: classification, run_id, parent_run_id/retry_reason, config_id,
code commit/tree, protocol SHA, registered config SHA, full config/data hash,
full scenario hash (including all Reliability levels and emergency prices),
seed, budget, method, environment/solver/version, UTC start/end, timing, status,
certification, objective/LB/UB/gap/signed_gap/gap_tolerance/exact violation,
trace hash and output hash. Missing unavailable fields are null, not fabricated.
The frozen nested engine audit retains its historical development label; the
outer N6 envelope always labels the actual use PILOT ONLY.

Save raw engine results and self-hashed envelope (hash excludes own hash field),
then file SHA manifest excluding itself. External Git commit/tree anchor source;
no recursive hash. Replay verifies exact inventory, safe unique relative paths,
regular files, hashes, source/config/scenario bindings, recomputes costs, all
scenario budgets/physical balances, and invokes unchanged N4 and N5 replay for
bounds/incumbents/phase legality including signed_gap and gap_tolerance.
Report failure integrity separately from successful mathematical certification.
Commit compact evidence with enough original traces/data to replay solver-free,
deduplicating/referencing only with explicit hash validation if used; no large raw
output directory. N5 forged-trace regression tests must still pass.

## Prespecified scientific diagnosis (not statistical inference)

MODEL: report all 16 M0/M1/M2 objectives and mechanism summaries; count y_F,
paid Reliability and nonzero emergency exercise; matched budget/risk/contract
changes in q, C_R, y_F, E and unused cash/resources. Explain same-B cross-stage
trade-offs. Distinguish equal objectives from equal arbitrary decisions.
Zero activation in some configs is valid. Flag serious model informativeness
risk if all M2 objectives equal M1 AND all M1 objectives equal M0 AND neither
paid Reliability nor Option activates across the entire registered coverage,
with absent meaningful q/environment response. Also report narrower persistent
nonactivation as a coverage/claim risk even when not a full blocking degeneration.

ALGORITHM: totals and per-config Phase I/II hits, Phase III/full/complete calls,
evaluations, additions, iterations, active size and runtime. Flag severe algorithm
risk if no Phase I/II hit in all cases, Phase III every iteration, no paired
oracle/evaluation reduction, and median A1/A0 time >1.20. The 1.20 is a descriptive
warning threshold, not a speed hypothesis/test. Independently flag complete
Memory inactivity as a narrow mechanism coverage risk; no automatic redesign.
Slower A1 alone is not a blocker. No p-values or "A1 speeds up X%" paper claim.

Classify unexpected patterns as A economic scaling, B insufficient coverage,
C structural model degeneration, D A1 mechanism effectiveness, E small-sample
uncertainty. State observed configs, universality, plausible explanations, what
is and is not established. Serious risk => N6_SCIENTIFIC_INFORMATIVENESS_RISK,
pause N7, retain Draft PR. Correctness/engineering failure => N6_BLOCKED.
READY requires trustworthy execution/replay, no severe informativeness risk,
passing tests/CI and realistic capacity advice; external review still controls N7.

## Capacity projection and deliverables

Report per-method median and observed maximum wall time, iteration/oracle/evaluation
ranges and output bytes; Python/native-memory caveats. Project illustrative
100 and 1000 A0/A1 PAIRS at measured median and observed worst-case cost/storage,
plus a clearly labelled 2x planning contingency (not a statistical upper bound).
These counts are planning units, not an N7 matrix. Include preflight/audit/startup
overhead separately. Size probes only support 12-to-24 scenario local observations,
not a general asymptotic extrapolation or OOS capacity estimate. If expensive,
suggest reducing noncore repetitions/levels in N7 without dropping E2–E6 questions.

Deliver protocol, fixed configs, isolated runner, fault-path tests, compact
manifest/evidence/hashes, N6_PILOT_REPORT.md and N6_SCIENTIFIC_DIAGNOSIS.md.
One branch n6/pilot-readiness, one Draft PR #7, no merge and no N7/N8 work.

