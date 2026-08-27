# N5 A1 correctness report

## Scope and protocol freeze

A1 is Memory-Guided Three-Phase C&CG. This stage establishes EF=A0=A1 correctness,
not speed, scientific effect or publishable novelty. No N6 pilot, N7 formal freeze
or N8 experiments are performed. No N0–N4 files are modified.

Base is merged N4 commit `7c45ccb7223a1733361ecc9fcbd63d34feb8d139`, tree
`ec3115232b535967ba5d07502cdab58bd5a24775`. Git transport was unavailable during
initial synchronization. The exact GitHub-verified merge object was retrieved via
API, reconstructed only after its full Git object SHA matched, and fast-forwarded
locally; all parent/tree objects already existed. No history or content was invented.

N5 protocol was independently committed before A1 implementation or results:

- `docs/N5_A1_PROTOCOL.md`
- Freeze commit: `86dfd0da16fbae52ed8ade842999cc89cc4d09e2`
- SHA-256: `c674f64297e6ad47fca0feeb593cd31202f370a6c567d5620d7f26ccab360a12`
- N4 protocol remains unchanged at SHA-256
  `f3c4d4ee2d352b4b5666cfb505a6fd5d61f0d2cdff7a15ab6c6a1f0a2ec0a72f`.

The fixed N4 threshold is 1e-7+1e-9*max(1,abs(a),abs(b)). Its solver options,
optimality acceptance, raw feasibility, recourse and worst-ID rules are unchanged.
M2, the EF, A0 and exact oracle are reused directly, not forked or reimplemented.

## Files and control flow

Within `src/robust_budget_allocation/algorithms/`:

- `a1_memory.py`: solve-local bounded exact-history entries, pruning, inspection
  order, updates and eviction.
- `a1_candidates.py`: deterministic current-quantity exposure proxy, pool,
  exclusions, ranking and selection budget.
- `memory_guided_ccg.py`: A1 restricted-master and three-phase state machine,
  N4 runtime/oracle reuse, structured trace and bound/incumbent handling.
- `a1_verification.py`: solver-free replay of every phase, memory transition,
  score/rank, first-hit rule, source, bound, incumbent and full certification.

`tests/test_n5_a1.py` covers lifecycle, three-way real solver correctness and
fault-injected state paths. `tests/fixtures/n5_correctness.json` contains all 15
unchanged N4 input cases and one additional hand-designed state-machine case.
`scripts/n5_a1_correctness.py` is a one-shot clean-commit development evidence
command, not a pilot/formal runner. It stops on genuine correctness failure.

Every iteration solves the shared N4 restricted master, updates LB from its
accepted solver lower bound, then runs MEMORY -> CANDIDATE -> FULL_EXACT until
either a fresh violation is added or full certification is obtained. Memory and
candidate hits skip later phases and begin the next master iteration. They never
update global UB, set certified, or reuse stale losses as current recourse.

## Memory and candidates

Memory starts empty inside every solve. There is no initial-memory API or shared
cache across runs, seeds or instances. Entries contain scenario ID, full data SHA,
last exact loss/iteration/source. All successful phase evaluations are recorded;
Phase III includes non-worst scenarios that may matter at a later decision.

Capacity is 8, maximum age 4 iterations, inspection budget 2. Retention favors
newer observations, then higher loss, then canonical ID. Inspection favors higher
historical loss, then recency, then ID. Stale, mismatched, malformed, future or
nonfinite entries are removed with reasons. Active entries are retained for audit
but skipped for addition. Every inspected loss is freshly solved at current q/z/y.

Phase II excludes active and already-inspected IDs. The frozen score is
`s*max(d_w-sum(rho_jkw*q_jk),0)`. It ignores emergency price/Option adjustment and
is not Q_w or a UB. Ranking is descending score then ascending canonical ID;
evaluation budget is one candidate. No timing, future oracle value, another run
or hidden weight is used. Empty/exhausted pools fall through to full exact.

These constants/formula were not tuned on timing or correctness results. A1 can
incur overhead or be slower. Neither acceleration nor new scientific conclusions
are claimed in N5. Compared with legacy cross-budget history transfer, this is
run-local exact-history memory plus a separate proxy search and certification gate;
the operational difference is not itself evidence of research novelty.

## Exactness, accounting and failure handling

Only Phase III invokes N4's complete `exact_oracle`. Its proof must contain every
Omega ID once, exact optimal statuses, matching data/decision identity, recomputable
recourse and canonical worst ID. Only then can first_cost+worst_loss update UB.
The minimum UB retains its actual producing iteration/first stage/full oracle;
exact ties retain the earlier incumbent. Before any Phase III, UB/gap are null.

The final certificate requires the just-completed Phase III's maximum violation
and the global LB/UB gap to satisfy unchanged N4 thresholds. Historical UB may
remain visible during memory/candidate hits but cannot be changed there. Every
saved trace can replay this restriction independently of stored hit/score flags.

Duplicates are excluded before evaluation; inconsistent duplicate selections
return convergence_failure. Full-oracle repeated violated active scenarios also
fail, never loop. Solver errors, locallyOptimal, time/iteration limits, partial
oracles and numerical failures never become certified results. Inspection failures
are oracle_failure with the underlying cause, not ordinary misses or fallback.

N1 preflight remains cached once per process. EF/A0/A1 use the same Python 3.12.10,
Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct, Threads=1, MIPGap=MIPGapAbs=0
and N4 tolerances. No solver fallback is present. A real integration test checks
one preflight across all three algorithms.

## Correctness and state coverage

The 15 N4 cases cover Reliability/Option mechanisms, binding cash/cap, unused
resource/budget, canonical worst ties and multi-round additions. The additional
`history_after_buffered_candidate_miss` hand case has an initial unavoidable
emergency need, a high-demand but cheap buffered scenario, and two supplier-specific
needs. The proxy ranks the buffered scenario first; it is nonviolating. Full exact
then adds the first-supplier scenario and memorizes the second-supplier need.

At the next master, memory finds the second-supplier scenario. It adds that scenario
without Phase II/III or UB update: UB remains 121 from the earlier complete proof.
The final objective is hand-verifiable as regular cost 0.6*(11+10)=12.6, Option
fee 1 and worst recourse 10, totaling 23.6. The last full oracle certifies this.
This is mechanism/state coverage, not a selected favorable performance instance.

Additional tests cover candidate hits with no UB, memory/score ties, active
duplicates, empty/exhausted pools, stale/invalid memory and TTL boundary,
capacity/eviction, actual fresh-run replay, solver/partial-oracle failures and
iteration-limit failure after a candidate hit. All original N2–N4 tests remain
unchanged, including both nesting relations and EF=A0.

## Audit, execution evidence and review gate

The evidence command requires tracked inputs, a clean execution commit, no untracked
scientific files and unchanged commit/tree over execution. Every result binds
environment, code/source, full data/config, scenario order/hash, N4/N5 protocol
hashes, solver outcomes and status. Output is atomic and cannot silently overwrite
existing evidence. All records are development/correctness_evidence.

Clean-source execution completed with all 16 three-way cases PASS:

| Case | EF = A0 = A1 objective | A1 iterations | Memory hits | Candidate hits | Phase III calls |
|---|---:|---:|---:|---:|---:|
| reliability_no_value | 4 | 1 | 0 | 0 | 1 |
| reliability_value | 6 | 1 | 0 | 0 | 1 |
| reliability_too_expensive | 8 | 1 | 0 | 0 | 1 |
| option_no_value | 4 | 1 | 0 | 0 | 1 |
| option_value | 5 | 1 | 0 | 0 | 1 |
| option_unexercised_scenario | 5 | 1 | 0 | 0 | 1 |
| option_cap_binding | 24 | 1 | 0 | 0 | 1 |
| remaining_budget_binding | 24 | 1 | 0 | 0 | 1 |
| expensive_emergency_no_exercise | 31 | 2 | 0 | 1 | 1 |
| unused_resource | 6 | 1 | 0 | 0 | 1 |
| joint_reliability_option_accounting | 8 | 1 | 0 | 0 | 1 |
| arbitrary_four_levels | 5.8 | 1 | 0 | 0 | 1 |
| heterogeneous_supplier_levels | 4 | 1 | 0 | 0 | 1 |
| three_round_cross_failures | 8 | 3 | 0 | 2 | 1 |
| equal_worst_canonical_id | 50 | 1 | 0 | 0 | 1 |
| history_after_buffered_candidate_miss | 23.6 | 3 | 1 | 0 | 2 |

Maximum three-way absolute objective difference: 0. Maximum relative difference: 0.
Maximum final A1 gap and full-oracle violation: 0. All 16 returned incumbents have
valid full-Omega feasibility proofs bound to their producing Phase III. No partial
evaluation generated a candidate/global UB or convergence certificate.

A1 diagnostics total 21 iterations, 1 Phase I hit, 3 Phase II hits, 17 Phase III
calls, 17 complete exact-oracle calls and 38 scenario evaluations (all phases).
These counts are not an algorithm performance conclusion or a reason to retune.

- Execution code commit: `f3e85a1dfd1bc19e8a709b39829908564a0019d1`
- Execution code tree: `b73d74cf9ebf636cbe4c427e3bd2f3cec4e7c09b`
- Evidence: `docs/evidence/N5_EF_A0_A1_CORRECTNESS.json`
- Evidence SHA-256: `9a2f74b12c89659210ad93ae91e53ff8749d6fe45d03a93bf542e935634e7df3`
- Fixture SHA-256: `a18ed3cbe7fa1c273a3df5614c1f58db77496e90ecfc4139ddddbd114f3816bc`
- Real environment/preflight: PASS; exact locked versions and Threads=1 as above.
- Test inventory: 553 tests, 455 solver-free and 98 licensed. The original 463
  N0–N4 tests are unchanged. N5 adds 52 implementation/state tests and 38 saved
  evidence/hash/replay tests. Positive saved evidence uses real solves; negative
  fault-injection tests are separately labeled and never counted as successful
  scientific solves.
- Review refresh: local solver-free 455 passed (98 deselected); local licensed
  98 passed (455 deselected). All saved three-way records are real licensed runs.
- Existing CI automatically discovers the new tests without changing its frozen
  workflow. Exact tested SHA and hosted solver-free checks are on Draft PR #6;
  remote licensed CI remains explicitly gated and may be skipped. Local licensed
  verification is separate from hosted CI success.

`tests/test_n5_evidence.py` replays every saved score, rank, memory transition,
first-hit choice, partial-phase UB restriction, full certificate and incumbent.
It rejects forged partial UB, skipped certification, future memory, scores/ranking,
truncated Omega proofs, incorrect incumbent binding and altered call counts.
All 15 N4 input cases are checked byte-equivalently as parsed JSON within the new
fixture collection. Historical source files and inventories are unchanged.

`docs/N5_A1_HASHES.sha256` covers the exact 11 N5 content files, excluding itself.
Protocol/code commits and the final artifact commit/tree are external anchors,
not recursively self-hashed artifact commits. N0–N4 hashes remain intact.

## PR #6 external-review correction: hit-phase gap replay

The external review identified an audit-only omission: Phase I/II hit replay
checked the clamped historical gap but not its signed value or tolerance. Four
new negative tests reproduced acceptance of forged signed_gap/gap_tolerance
before the fix. They now reject both historical-UB memory-hit tampering and
non-null fabrication on a candidate hit before any full UB exists.

The verifier now requires all three fields (gap, signed_gap, gap_tolerance).
Without a historical UB all must be explicitly null; with a UB all three are
recomputed under the unchanged N4 tolerance. Six additional negative tests
reject omission of any field in either branch. The trace producer initializes
the two previously omitted fields to null. This is a serialization change only;
no solver, bound update, scenario selection, memory/candidate rule, protocol or
convergence decision is changed.

The 16 cases and all 21 iterations were regenerated from the new clean code
commit and compared to the previous evidence: after normalizing explicit nulls,
source audit and runtime metadata, all scientific values and trace decisions
are identical. Old evidence remains recoverable in Git at `fe3b64ca8ed66a34d943166e21545bae9f5574af`.
Maximum objective difference/gap/violation remain zero and diagnostics remain
1/3 phase hits and 17 complete oracle calls. This fixes replay completeness,
not an error in the previously reviewed A1 solutions.

No specification conflict or scientific N6 blocker is currently identified.
N6 still requires external review, approval and merge of Draft PR #6, and its own
pre-entry registration of pilot parameters/seeds/runtime/iteration safeguards.
No N6 pilot work has started.
