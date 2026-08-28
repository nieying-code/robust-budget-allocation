# N6 fresh full pilot restart and governance incident

N6_EXECUTION_AUTHORIZED. N7_NOT_AUTHORIZED. PILOT ONLY.

"N6 PR #7 was merged prematurely before full pilot completion. This merge is a governance event only and does not constitute N6 scientific approval, readiness, or authorization to enter N7."

- Prior PR: https://github.com/nieying-code/robust-budget-allocation/pull/7
- Merge commit / restart base: ce12e391f503ca877605f860256a1f86e11d59d8.
- Merge timestamp: 2026-08-28T02:22:07Z (Asia/Shanghai 2026-08-28 10:22:07).
- Merged by: nieying-code. State at merge: N6_BLOCKED / paused; the isolated
  harness diagnostic passed, but the full pilot was NOT complete.
- Historical n6pilot01: 3 attempted, 2 accepted, 1 incomplete, 77 unattempted.
- Historical n6diagnostic01: one EF diagnostic, not a scientific group.
- The merge is preserved without deletion, rollback, rewriting or force push.

## Current user authorization

Create branch n6/pilot-restart from current main above and a new Draft PR,
N6 Fresh Full Pilot Restart. Preserve all historical evidence. Restore only the
controlled full-pilot entry and independently commit before scientific runs.
Use fresh batch n6pilot02 from the first M0, all 16 registered configurations and
80 runs in frozen order (M0, M1, M2 via EF, A0/A1 with registered alternation).
M2 is the EF run, not a sixth method or an additional 16 runs.
Do not reuse any old/diagnostic result. Do not edit protocol/config, models,
algorithms, solver settings, tolerance, watchdog, or maximum iterations.

All 80 runs must share one new clean execution commit/tree and exact source
manifest. Before the first scientific run, rerun solver-free tests, real licensed
tests, Windows heartbeat stress, environment preflight and source/protocol/config
hash verification. Any failed gate prevents pilot launch. Any non-certified run
or failed audit stops the entire batch; retain evidence, no retry, skip, seed
replacement, timeout change, overwrite or continuation. Full scientific diagnosis
and capacity projection require 80/80 completion. Otherwise report the stop.

The new PR stays Draft even after 80/80 success. External review of its full
evidence determines N6 approval; neither the earlier merge nor this execution
authorization grants N6 readiness, N7 entry or formal experiment authorization.
