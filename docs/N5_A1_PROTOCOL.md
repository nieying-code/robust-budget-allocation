# N5 A1 protocol v1 — pre-result freeze

Freeze this document in an independent commit before A1 implementation/correctness
results. A1 is Memory-Guided Three-Phase C&CG, not a new optimization model.
No scoring/budget/lifecycle choice is selected using runtime results. These choices
remain fixed through N5 and the later pilot; no speed claim is made here.

## Shared mathematical and numerical contract

M2, EF, A0, the N4 master builder, fixed-decision scenario evaluator, full exact
oracle and solver runtime are reused without changes. The N4 correctness protocol
SHA-256 is `f3c4d4ee2d352b4b5666cfb505a6fd5d61f0d2cdff7a15ab6c6a1f0a2ec0a72f`.
Its T(a,b)=1e-7+1e-9*max(1,abs(a),abs(b)), solver acceptance, bound crossing,
economic accounting, canonical recourse and worst-ID rules are unchanged.

As for A0, the initial active set is exactly the smallest canonical scenario ID.
IDs are ordered by Python string Unicode code points. Active sets grow monotonically,
are unique, and are stored in canonical order. No first-stage tie-breaking objective
is added. Equivalent optimal first-stage vectors are accepted using separate full
recourse feasibility and objective certificates, not arbitrary vector equality.

## Memory entry, lifetime, update and inspection

- A fresh empty memory is created inside every solve call. It is never supplied by
  a caller, persisted for reuse, shared across solves/threads, or imported from A0,
  other instances, seeds, runs, validation, OOS or future iterations.
- One entry per scenario ID stores full instance data SHA, last exact loss,
  last evaluated iteration, and last source MEMORY/CANDIDATE/EXACT. No cached loss
  is treated as the value at the new master decision.
- Successful exact evaluations from all three phases enter/update memory after
  that phase. A complete Phase III imports every evaluated scenario, including
  non-worst/nonactive scenarios; these may become valuable at a later master.
  Active/worst history may remain stored, but active IDs are never eligible to add.
- Capacity is 8 entries. Retain entries sorted by descending last iteration,
  descending last loss, then ascending ID; evict the remainder. No tuning.
- At the start of iteration r, remove entries with unknown IDs, mismatched instance
  SHA, malformed/nonfinite/negative loss or iteration, a future/current iteration
  timestamp, invalid source, or age r-last_iteration>4. Record each removal reason.
- For inspection, skip active IDs (record the skip). Sort remaining entries by
  descending last loss, descending last iteration, then ascending canonical ID.
- Inspect at most 2 entries in that order using the unchanged N4 exact scenario
  evaluator at the *current* master decision. Stop at the first exact violation
  max(0,Q-eta)>T(Q,eta). On a hit add this nonactive scenario with source MEMORY
  and proceed to the next master iteration. Neither Phase II nor III runs then.
- Update all successfully evaluated entries even on a miss, preserving the raw
  evaluation evidence. A solver/numerical failure is fatal, not a cache miss.
  Memory is discarded on solve termination; trace snapshots are audit only.

## Candidate pool, scoring, ranking and selection

Phase II runs only if Phase I has no eligible violation. Candidate pool is all
Omega IDs not active and not actually evaluated by Phase I in this iteration.
This excludes a redundant same-decision solve; uninspected memory IDs can remain.
Record active/already-inspected exclusions, the full eligible pool and ranking.

For each eligible w compute the fixed proxy

    score_w = s * max(d_w - sum_jk rho_jkw * q_jk, 0).

It uses input demand/fulfillment and current q only. It ignores Option exercise
and emergency price deliberately: it is unadjusted shortage exposure, not an
oracle answer or a UB. It does not consult present/future full-oracle results,
other runs, timing measurements, or hidden learned weights.

Rank by descending score, then ascending canonical ID. Evaluate at most 1 candidate
using the N4 exact scenario evaluator. If its exact violation exceeds T(Q,eta),
add it with source CANDIDATE, update memory, skip Phase III and proceed to next
master iteration. Otherwise update memory and fall through to Phase III. Empty
or exhausted pools are misses, never convergence. No random sampling is used.

## Three-phase state machine and exactness boundary

MASTER -> MEMORY -> (hit: ADD/NEXT; miss: CANDIDATE)
CANDIDATE -> (hit: ADD/NEXT; miss/empty: FULL_EXACT)
FULL_EXACT -> (certified: STOP; new violation: ADD/NEXT; failure: FAIL).

Memory/candidate selection is based on a fresh accepted scenario solve. Before
adding, confirm membership in Omega and absence from active. Normal active entries
are skipped before evaluation; an inconsistent duplicate selected by an internal
component is convergence_failure, never repeated progress. Malformed/nonfinite
scoring is numerical_failure, not permission to silently substitute another method.

Only Phase III calls the unchanged N4 `exact_oracle` on *all* Omega. Only a complete,
optimal, current-decision/data-bound proof may generate candidate_UB=first_cost+max Q.
Validate its proof with N4 `validate_oracle`. Keep the minimum such UB with its
exact producing iteration, first stage and full oracle. On exact equal UB retain
the earlier incumbent. Phase I/II never update candidate/global UB, even if their
evaluations incidentally cover all currently omitted scenarios.

LB is the running maximum accepted master solver lower bound, exactly as in N4.
Phase I/II may update LB and record an existing historical UB/gap, but cannot set
convergence/certified. With no prior Phase III, UB/gap/incumbent are null, not a
fabricated finite bound or JSON Infinity.

Only a just-completed Phase III may certify: signed global gap must be within
[-T(UB,LB),T(UB,LB)] and current full maximum violation <=T(max Q,eta). A new
canonical violating worst ID is added with source EXACT; an already-active worst
with failed gap/violation, or no new violated scenario when gap fails, is an explicit
convergence_failure. Materially crossed bounds are numerical_failure.

The sole search fallback after ordinary memory/candidate misses is full exact
certification, not another solver, model, algorithm or tolerance. No auto-retry of
failed solvers as success. Default iteration safeguard is len(Omega)+1 (same A0);
an explicitly smaller positive integer is allowed for negative tests. Exhaustion
is iteration_limit even after a Phase I/II hit, never certified success.

## Failures, audit and tests

Master failures retain N4 statuses. Phase I/II/III evaluator failures return
oracle_failure with underlying status and partial trace; they cannot update UB.
Malformed proof/scoring, nonfinite results and crossed bounds are explicitly
non-success. Local optima, errors, time/iteration limits and unknown outcomes
never certify. N1 real-license preflight remains process-cached outside solve timing.

Each iteration records active IDs and INITIAL/MEMORY/CANDIDATE/EXACT addition
history; master status, primal/bound, eta, q/z/y and LB; memory before/after pruning
and evaluation, removals/evictions, inspection scores/order/rows/hit; candidate
pool/exclusions/scores/ranking/evaluations/hit; Phase III called or skipped and its
complete oracle if called; legal candidate UB or null, global UB and producing
iteration, gap, violation, added ID/source, status and certification. Failed/omitted
phases are explicitly distinguishable. Counters count actual calls/evaluations.

A solver-free replay must reconstruct memory transitions, scores, first-hit
selection, additions, bounds/incumbent and final full-oracle certification from
the trace and input. Provenance binds code commit/tree, N4/N5 protocol hashes,
full data/config/scenario hashes, real environment, solver outcomes and status.

Use all N4 cases and additional hand cases for state coverage, not speed tuning.
Test memory hit, candidate hit, Phase III violation/convergence, duplicate active
entries, score/worst ties, empty/exhausted pools, stale/mismatched memory, solver/
oracle failures, iteration exhaustion, deterministic replay and fresh solve memory.
Positive evidence requires EF=A0=A1 within unchanged N4 tolerances and complete
feasible incumbent proofs. Run all N2–N4 regressions. Any genuine A1 correctness
failure is N5_BLOCKED; do not change M2 or loosen tolerances to manufacture success.

The old legacy algorithm transferred active/history across budgets and called a
full oracle each round. This A1 has run-local exact-history entries, a separate
current-decision proxy ranking, and explicit full-certification gating. This is
an operational distinction, not proof of publishable novelty or acceleration.
Runtime/hits/call counts are development diagnostics only. No N6/N7/N8 work is
authorized until the respective external review and freeze gates.
