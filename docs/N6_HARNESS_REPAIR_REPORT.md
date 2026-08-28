# N6 harness repair and single diagnostic follow-up

Status before the conditionally authorized retry: engineering validation PASSED
(550 solver-free, 100 real licensed tests; three Windows stress bursts passed).
The ONE authorized EF diagnostic subsequently PASSED; outcome is appended below.
Full pilot resume, another diagnostic and N7 remain NOT AUTHORIZED.

## Scope and implementation

Only N6 execution/audit code and its tests/docs change. No N0–N5 file, model,
algorithm, solver option, tolerance, candidate value, seed, budget or scenario
formula is changed. The original N6 archive and failed directory stay intact.

- heartbeat.py: fixed absolute monotonic deadlines; eight-attempt/0.5s bounded
  retry only for read PermissionError/FileNotFoundError. Last valid stage is
  retained. Original worker phase-start timestamps prevent a delayed observation
  from extending a new deadline. Malformed JSON/other errors fail immediately.
- execution.py: persist complete read-error context and cleanup outcomes, inspect
  the final heartbeat even after process exit, return actual post-cleanup exit
  code; refuse old worker output directories before any write. Windows tree
  cleanup uses owned-PID taskkill /T; isolated Unix worker groups receive SIGTERM.
- storage.py / diagnostic.py: authenticated cross-batch parent lineage, immutable
  parent proof, fixed EF-only scope, a durable single-use authorization claim.
- scripts/n6_pilot.py: full matrix run entry disabled; diagnostic-retry allows no
  config/batch override and returns after exactly one authorized attempt.
- replay.py / source_archive.py: validate historical source against the recorded
  commit/tree and recompute Git-object IDs, including in shallow CI using a
  compact source-object proof. No historical source is executed. Frozen N1 CI
  remains unchanged. Diagnostic records are rejected by scientific group replay.

## Pre-diagnostic tests and observations

Synthetic tests exercise short read conflicts/recovery, persistent conflicts,
fixed deadline expiration, malformed/nontransient errors, detailed context,
process-tree/grandchild lease release, duplicate run/claim rejection, immutable
cross-batch lineage, old worker protection, historical source tampering and
disabled full-pilot CLI.

The first Windows stress fixture requested 2,000 atomic replacements within a
30-second synthetic deadline. All three probes correctly stopped at that
deadline after approximately 593–613 writes; no scientific run occurred.
An intermediate 500-write fixture still timed out in two of three probes.
The N6-only reader now requests FILE_SHARE_READ|WRITE|DELETE and keeps a stable
handle to one atomic version. This alone did NOT make 2,000 writes fit 30 seconds.
The remaining Windows contention source is not proven. See CreateFileW semantics:
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
A separate synthetic measurement observed 100 writes / 113 N1 replacement
retries / 6.21 seconds with concurrent reads; forcing 2,000 writes was a throughput
requirement, not a necessary correctness criterion. The final stress test is
therefore THREE fixed 10-second continuous-write/read bursts, retaining the SAME
30-second watchdog, requiring at least 50 replacements and 100 reads per burst,
and reporting actual writes, reads, recovered conflicts, exit and lease release.
No count or runtime is represented as an algorithm-performance result. Neither
solver nor pilot deadline changes. All failed preliminary stress outcomes are
retained here; the original pilot race's precise root cause remains unproven.
Final full regression: 550 solver-free and 100 real licensed tests passed.
All three Windows stress bursts passed, including clean worker exit and released
leases. Detailed actual counts and tested source hashes are stored in
docs/evidence/N6_HARNESS_VALIDATION.json before the diagnostic run.

## Diagnostic authorization and interpretation

Parent: n6pilot01/n6pilot01-00-ef.
New run: n6diagnostic01/n6diagnostic01-ef-retry.
Reason: supervisor heartbeat I/O diagnostic after approved harness repair.
Purpose: harness_diagnostic_only. Use precisely the parent configuration and
settings, with a new clean source anchor. Never pool it with old M0/M1.

Even if it passes, this proves only that this single repaired supervised EF
attempt completed; it neither proves the original race's exact root cause nor
finishes N6 scientific diagnosis. No A0/A1, capacity, sensitivity, or paper claim
can be derived. Stop for external review on the same Draft PR #7.

## Single diagnostic outcome — execution stopped after this attempt

The conditional prerequisites were met and committed before launch:
execution commit 01cd346d60c2bb0fcf6731f2c9806e17b47e3d57,
tree a5f6a96a005bf4076873c59aefcf5709cbf7ad0a; source gate was clean.
The recorded source-input hashes exactly match the pre-diagnostic validation.
Protocol/config/seed/budget/scenarios/solver/tolerances equal the failed parent.

- New run n6diagnostic01-ef-retry: success/certified; worker exit 0.
- End-to-end supervisor wall: 3.180571799981408 seconds.
- Frozen EF call runtime: 0.35578520002309233 seconds; NOT comparative evidence.
- Preflight: 0.1804565999773331 seconds, outside algorithm timing.
- Heartbeat read conflicts: 0; final stage complete; cleanup success=true,
  attempted=false because the worker exited normally. No exception was observed.
- Objective=LB=UB=495.7182976095696; gap=signed_gap=exact_violation=0;
  gap_tolerance=5.957182976095696e-7. Solver-free certificate/accounting replay PASS.
- Compact archive docs/evidence/N6_EF_DIAGNOSTIC_RETRY.json.gz: 23,595 bytes,
  SHA256 7478809a666e27cbeac9aa6917d5d0e032a925d62f8c1f8c4ff777d737da53bf.
- Parent remains incomplete/certified=false. Read-only comparison of ALL THREE
  old run directories against the reviewed archive found them unchanged.
- Old/new source proofs are separately authenticated; this EF is explicitly
  rejected as a scientific group member. Completed configurations/pairs remain 0.

Only one diagnostic attempt occurred. The one-use authorization is consumed;
the remaining 77 pilot runs were not started. No A0/A1 comparison or N8 capacity
projection exists. Scientific informativeness remains NOT ASSESSABLE. A single
conflict-free success does not establish the precise original race root cause.
N6 remains paused for external review; do not interpret diagnostic PASS as N6
READY or authorization to restart. N0–N5 and the frozen N6 protocol/config remain
unchanged. Post-run work is limited to solver-free artifact replay, docs, hashes,
and the existing Draft PR #7. CI outcomes are attached to its final artifact SHA.

Final artifact verification: 12 new saved-diagnostic tests passed, including
re-sealed scope/lineage forgeries and old/new source replay without local Git
history. The complete solver-free regression passed: 562 passed, 100 deselected
(52.37 seconds), including the Windows synthetic stress checks again. The first
post-artifact test command accidentally used the nonexistent marker `licensed`
instead of `gurobi`; that unit-test invocation was interrupted, its process tree
was checked absent, and it is not counted as a passing suite. It launched no
additional pilot run. The correct `not gurobi` run above supplies final regression
evidence. Pre-diagnostic real licensed validation remains 100/100 on the identical
execution source; no new scientific execution was requested after the diagnostic.
