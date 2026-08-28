# N7-pre mechanism confirmation — prelaunch stop

N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS

## Status and governance

STOP: prelaunch engineering/source gate failed; **0 scientific runs, 0/54
configs**. Layer 1 and Layer 2 have not started. This is not an Option Gate FAIL
or INCONCLUSIVE result, and not a model/correctness mismatch. No scientific Gate M
status can be assigned without the registered 18-config Layer 1 evidence.

N6 was formally closed by the user after PR #8 merged. N6 merge/base is
17994d9467cb265e032b5aee1b5dc843b9ae3f7c (2026-08-28T07:46:00Z).
New branch: `n7-pre/option-memory-confirmation`.
New Draft PR: https://github.com/nieying-code/robust-budget-allocation/pull/9.
No N7-pre changes were mixed into PR #8. N6 raw evidence, frozen N0–N6 files and
all existing model/algorithm implementations are unchanged. Earlier premature
PR #7 merge history remains preserved, not scientific authorization.

## Immutable registration and attempted execution anchor

Registration commit: 4df5d90c8a3bd5a131cd47f8f7baba55e90773ac.

| Item | SHA256 |
| --- | --- |
| Protocol | b110e1ecf24b83c2fa217204bb35177be72cc13da57ef7e8d7b81d14b1497b1e |
| Full 54-config matrix | b25eea24b3610c0635262fae2549958d16058ff7a3f2aad8ae31fe44a9d10d16 |
| Six-seed registry | 5af50e8c337691652bd9045e4957c5fc61778aa096778fcedf0ba8791dd8e71b |

Seeds: 4289336819, 2954552515, 414623883, 2596770366, 799209694, 304170811.
All 54 configs were committed before any results. No registration changes followed.

Attempted execution commit: 21e217a974e82027364494b2a2342562786ed526.
Tree: f577262b7838976878c28dffe7e6a244a03dabba.
Git tracked worktree was clean at launch. This is **not a successful scientific
execution anchor**: the stronger source gate rejected ignored, untracked content.
Later reporting/evidence commits are delivery anchors, not execution runs.

## OBSERVED — failure and retained evidence

The single command `.venv\Scripts\python.exe scripts/n7_pre.py gates` exited 1.
`gates()` called `source()` before creating the validation directory; N1
`validate_source_state()` raised `RuntimeError` for five files below
`src/robust_budget_allocation.egg-info/`: PKG-INFO, SOURCES.txt,
dependency_links.txt, requires.txt and top_level.txt.

The files were already present (observed last-write dates 2026-08-26).
`.gitignore` ignores `*.egg-info/`, but N1 deliberately checks all untracked files
under supplied scientific roots, including ignored files. The new adapter passed
the broad `src` root. This explains how an ordinary clean `git status` coexisted
with a failing scientific-source gate. N1 validation was not bypassed or changed.

`outputs/harness-validation/n7-pre-v1` and `outputs/n7_pre/n7pre01` do not exist.
No test subprocess, license solve, preflight or scientific worker was started by
this command. No source repair, deletion, retry or alternate launch followed.

Retained evidence:

- `docs/evidence/N7_PRE_ENTRY_FAILURE.json`: exception, original call frames,
  command/exit, subsequent read-only file hashes and environment/package metadata.
  It explicitly discloses that original stderr existed in the tool transcript,
  not a separately saved entrypoint log; the command was not rerun to recreate it.
- `docs/evidence/N7_PRE_ENTRY_SOURCE.json.gz`: post-failure read-only source
  manifest and authenticated Git objects for the attempted clean commit/tree.
  It is code provenance, **not** evidence that the source gate passed.
- `docs/N7_PRE_DELIVERY_MANIFEST.json` and `docs/N7_PRE_HASHES.sha256`:
  exact delivery inventory/hashes; hash list excludes itself, Git commit/tree are
  external anchors. No prior evidence was overwritten.

## INFERRED — engineering diagnosis only

This is a new harness input-root/packaging-metadata integration issue, not evidence
about the frozen models or solver. Future repair should explicitly distinguish
declared scientific input paths from packaging metadata while retaining checks
for genuine untracked scientific inputs, with a production-entry regression test.
This report does not implement or authorize that repair, delete the metadata,
relax N1, or repeat prelaunch validation. Independent review is requested first.

## Tests and execution readiness

Before the attempted entry, 82 new solver-free unit tests passed (5.29 seconds in
the last recorded targeted run). They cover all 54 data/config domains,
generation, seed partition, Option criteria, full-cell Gate M, Memory opportunity
rules, genuine temporary-Git object proofs and persisted production gate
validation including forged source/XML/object rejection.

Those unit tests did **not** establish launch readiness in the actual editable
installation. The root/packaging collision was an integration coverage gap.
Additional post-stop evidence/regression tests diagnose this exact condition in
a temporary repository; they are not a new prelaunch attempt or scientific run.
Post-stop targeted regression: **86 passed in 5.97s** (82 original new tests plus
4 entry-evidence tests). Authenticated code proof and **17/17 delivery hashes**
passed. No scientific trace replay exists because no scientific run occurred.
Full clean-anchor solver-free and licensed prelaunch gates: NOT STARTED.
Environment preflight: NOT RUN. Read-only metadata reports Python3.12.10,
Pyomo6.10.1 and gurobipy13.0.2; license/Optimizer runtime is not newly certified.
PR CI is engineering regression only, not scientific/prelaunch authorization;
see the current PR checks for the delivery commit. No licensed rerun is claimed.

## NOT ESTABLISHED — model/algorithm diagnosis

| Economic-condition cell | Completed | Effective Option count |
| --- | ---: | --- |
| F-favored x45 | 0/6 | NOT OBSERVED |
| F-favored x90 | 0/6 | NOT OBSERVED |
| F-favored x150 | 0/6 | NOT OBSERVED |
| Reference x45 | 0/6 | NOT OBSERVED |
| Reference x90 | 0/6 | NOT OBSERVED |
| Reference x150 | 0/6 | NOT OBSERVED |
| Balanced x45 | 0/6 | NOT OBSERVED |
| Balanced x90 | 0/6 | NOT OBSERVED |
| Balanced x150 | 0/6 | NOT OBSERVED |

Do not interpret unrun seeds as inactive outcomes or report 0/6 activation.
There are no EF/A0/A1 comparisons, Option value observations, Memory observations,
runtime/workload or capacity estimates. No causal risk/budget effects, thresholds,
activation probability, statistical significance or runtime superiority is claimed.
Memory remains unchanged; its diagnosis is NOT EVALUATED, not evidence of failure.

## Stop

Keep PR #9 Draft and wait for review of the entry failure and a subsequent repair/
relaunch decision. Do not merge, run remaining configs, change registration or
start N7 formal design/N8. No scientific conclusion is supplied for unrun data.
