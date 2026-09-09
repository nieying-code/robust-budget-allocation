# Final A1 spurious-infeasibility hotfix

Status: engineering hotfix ready for independent review.

This change is an implementation revision of `A1_FINAL_NO_MEMORY_V1`, not a new
scientific algorithm. The implementation revision is
`A1_FINAL_NO_MEMORY_V1_R1_WITNESS_GATED_INFEASIBLE_RETRY`.

## Root cause and evidence

The production exact recourse solver can report `INFEASIBLE` for a
mathematically feasible tight-boundary LP. The existing algebraically equivalent
scaled retry handled recognized numerical failures but did not consider this
solver status. The pinned PR #31 diagnostic at
`db9626f6bd7bc3a2f23cd0bcbe19f66900bbf5d4` established:

- 205 reproducible Final A1 failures;
- 284 scenario-level production `INFEASIBLE` outcomes;
- 284/284 conservative original-semantic witnesses feasible;
- 284/284 diagnostic scaled solves optimal; and
- 284/284 mapped-back original-semantic validations passing.

PR #31 remains a read-only engineering evidence source. No E2-A scientific
artifact or implementation was merged, cherry-picked, promoted, or modified.

## Generic repair

The exact oracle still uses the production LP first. An accepted optimum remains
on the original path. A recognized numerical failure retains the existing scaled
retry. For an explicit solver `INFEASIBLE` outcome only, the oracle now constructs
the deterministic conservative recourse witness `x=0`, with shortage covering
unmet demand. The witness is checked against every original recourse constraint
family.

If that witness is infeasible, the original solver result remains failed. If it
is feasible, it only authorizes the existing algebraically equivalent scaled
retry. The scaled optimum is mapped back and must pass the same original-semantic
validation used by the normal exact path before Full Exact Certification can use
it. A failed scaled solve or invalid mapped solution fails closed.

The witness has no objective and is never an optimum, recourse result, upper
bound, or certificate.

## Invariants

- Model, objective, budget semantics, scientific data and parameters: unchanged.
- Absolute and relative feasibility tolerances: unchanged (`1e-7`, `1e-12`).
- Candidate Search and Full Exact Certification: unchanged and share this oracle.
- Solver policy: unchanged.
- Algorithm paper identity: `A1_FINAL_NO_MEMORY_V1`.
- Memory execution, cache, ranking, and statistics: absent.
- Scientific optimization runs: 0.
- E2-B, E2-C, and E2-D runs: 0.

## Engineering replay

The deterministic replay harness reads the frozen PR #31 identities through
`git show` and writes aggregate engineering evidence only. It does not overwrite
or formally recertify E2-A results. The completed replay certified 205/205 cases,
observed exactly 284 witness-gated Full Exact Certification retries, and retained
the original first-stage identity for all 205 cases. Eight deterministic controls
that were already certified retained Q/F/R, objective, worst scenario, and a
passing certificate.

Machine-readable evidence is in
`docs/evidence/FINAL_A1_SPURIOUS_INFEASIBILITY_HOTFIX_REPLAY_v1.json`.
