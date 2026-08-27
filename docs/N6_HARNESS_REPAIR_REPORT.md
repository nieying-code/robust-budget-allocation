# N6 harness repair and single diagnostic follow-up

Status before the conditionally authorized retry: engineering validation PASSED
(550 solver-free, 100 real licensed tests; three Windows stress bursts passed).
Full pilot resume and N7 remain NOT AUTHORIZED. This report will append
the one diagnostic outcome without changing the frozen protocol/config.

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
