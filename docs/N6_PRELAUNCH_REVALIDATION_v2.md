# N6 prelaunch revalidation v2 — conditional execution authorization

N6_SOURCE_COMPARISON_REVIEW_PASSED.
N6_PRELAUNCH_REVALIDATION_AUTHORIZED.
N6_PILOT_RELAUNCH_CONDITIONALLY_AUTHORIZED. N7_NOT_AUTHORIZED.

Continue Draft PR #8. Restore ONLY gates/run/worker required for the fresh
n6pilot02 batch. Diagnostic retry remains disabled. The reviewed canonical
source-comparison logic, N1 manifest API, frozen protocol/config, scientific
models/algorithms, seeds, budgets, scenario settings, solver/tolerances,
watchdogs and iteration limits remain unchanged.

Commit entry restoration BEFORE all prelaunch checks. Use its clean commit/tree
as the unique execution anchor. New validation directory:
outputs/harness-validation/n6pilot02-prelaunch-v2.
Never overwrite the old n6pilot02 gates, source-repair validation or stop evidence.

In order: solver-free tests; Windows-only tests (all four existing Windows-only
cases); real licensed tests; three Windows high-frequency atomic heartbeat stress
cases; actual environment/solver preflight; source/protocol/config verification;
real saved-gates JSON roundtrip using the production validate_gates function.
The Windows-only suite and repeated heartbeat stress are separate recorded gates.

The final gate is not mocked: persist gates.json, reload UTF-8 JSON, validate
complete source contents/seal/Git inventory/environment/XML hashes. Record the
list/tuple representation difference and canonical equality. Also persist/reload
a negative source-content mutation with both source and outer seals recalculated;
the production validator must reject it. Save an independent roundtrip.json
PASS/FAIL record. A PASS gate candidate without a PASS roundtrip cannot launch.
Both execute and worker require the actual gate-file/source/roundtrip binding.

Any failed prelaunch gate stops without batch creation, automatic repair, retry,
or scientific execution. Retain gate files and complete error evidence. Report
the execution commit/tree, clean worktree, directory and all gate outcomes before
the first scientific run. Only all PASS authorizes creation of n6pilot02.

The fresh batch begins with first-config M0 and follows the unchanged 16-config,
80-run order. M2 uses EF; no sixth method is added. All runs share one clean source
anchor and no historical pilot/diagnostic result. Any non-success or audit failure
stops all remaining runs without retry/skip/reconfiguration. After start, execution
code cannot change. Only 80/80 success allows full scientific diagnosis/capacity
reporting. All results still require external review on Draft PR #8; never merge,
enter N7 or run formal experiments automatically.

PR #7's premature merge (ce12e391f503ca877605f860256a1f86e11d59d8,
2026-08-28T02:22:07Z) remains governance history only, not N6 scientific approval,
readiness, completion, N7 permission or formal experiment authorization.
