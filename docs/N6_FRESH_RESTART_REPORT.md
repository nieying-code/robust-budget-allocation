# N6 fresh restart report — pre-launch audit stop

**N6_BLOCKED. No n6pilot02 scientific run started. Keep PR #8 Draft.**

## Governance history (preserved, not approval)

"N6 PR #7 was merged prematurely before full pilot completion. This merge is a governance event only and does not constitute N6 scientific approval, readiness, or authorization to enter N7."

PR #7 merge / restart base: ce12e391f503ca877605f860256a1f86e11d59d8.
Timestamp: 2026-08-28T02:22:07Z (2026-08-28 10:22:07 Asia/Shanghai).
At merge, N6 was BLOCKED/paused: original batch 3 attempted/2 accepted/1 incomplete,
77 unattempted, plus one isolated successful EF diagnostic. No completed full
pilot or scientific approval. This history was not rewritten, reverted or force
pushed. New branch n6/pilot-restart and Draft PR #8 were created from this main.
The user authorized a fresh full restart, not N7 or formal experiments.

## Independent entry-restoration source and preregistration

- Governance commit: 76bd01566c95a2dd8301bf1daf72dbce2ddfbdec.
- Clean entry-restoration / intended execution commit:
  14da8abb5b0735bd5e180f1387d9b32f249fbb1d.
- Tree: 113ad6ffdfb59507b0c9064204adfbb0edf944a5.
- Source manifest SHA256: 5a2d5d73139648bc71de66a4d3f92cd4d46aee5a12dd2394d78883784605dc0a.
- Protocol SHA256: ba60833a951ea4ad69ba123ea421329a1387a0cf581645f8bc7040d0c3414b0d.
- Config SHA256: 974c5b9e13d278cff2ead221d1c838aff4db2c3c3b97314b2595ecb00d6db0d2.

Only N6 execution/audit entry and tests changed. Frozen protocol/config,
M0/M1/M2, EF/oracle/A0/A1, solver settings, tolerances, watchdog, iteration limits
and all 16 configurations/order remained unchanged. M2 is solved through EF;
the frozen plan is five methods per config, 80 runs, not 96.

## Engineering gates before the single launch invocation

All on the clean commit above, 2026-08-28T02:46:20Z–02:49:24Z:

| Gate | Result |
| --- | --- |
| Solver-free | 572 passed, 100 deselected; 65.53s |
| Real Gurobi licensed | 100 passed, 572 deselected; 82.06s |
| Separate Windows stress | 4 passed, 15 deselected; 31.74s |
| Environment preflight | PASS, real license available |
| Source/protocol/config checks during gates | PASS; clean source unchanged |

Python 3.12.10, Pyomo 6.10.1, gurobipy/Gurobi 13.0.2, gurobi_direct, Threads=1.
Stress includes three atomic read/replace bursts plus native Windows sharing-error
recovery. Pytest emitted three JUnit record_property-format warnings; these were
not test failures. Original raw XML and gates.json are retained unchanged under
outputs/harness-validation/n6pilot02 and losslessly embedded in compact stop
evidence. No solver fallback. Entry-commit Push/PR CI both passed; hosted licensed
job was explicitly skipped, separate from the real local licensed gate.

## Actual stop and exact local cause

One invocation of `scripts/n6_pilot.py run --batch n6pilot02` returned exit 1:

    ValueError: restart gate/source mismatch

Failure path: main -> execute -> restart.execute -> validate_gates, before batch
directory creation, worker spawn or any scientific solve. n6pilot02 did not exist
at the stop. The intended M0 first run never began. No retry invocation followed.

Read-only diagnosis at the same clean source established:

- Loaded gate source git.untracked_paths: list `[]`.
- Live build_source_manifest source git.untracked_paths: tuple `()`.
- Direct Python dictionary equality: false.
- Canonical JSON equality and manifest hashes: equal.
- Commit/tree, source files, configuration and environment had not changed.

The new restart entry incorrectly compares serialized and in-memory manifests
with direct Python equality. This is an execution-layer representation bug, not
scientific drift or a model/solver failure. New orchestration tests mocked the
gate validator; they did not cover the real JSON round-trip boundary. Passing
tests did not close that boundary. No production fix is applied after the stop.
External review must authorize any repair and subsequent launch. No N1 frozen
manifest API needs to be silently changed, and no frozen scientific definition
should change to address this execution issue.

## Counts, diagnosis and capacity

Planned 80; actual scientific runs 0; scientific successes 0; scientific failures
0; entry/audit failures 1; unattempted 80. A0/A1 pairs 0. No new run IDs/results
were fabricated. Historical n6pilot01 and n6diagnostic01 remain unchanged and
excluded. max |Z_A0-Z_A1|, mechanism activation, structural response, Phase I/II/III,
oracle/evaluation workload, algorithm timing and N8 storage/runtime projection
are NOT AVAILABLE from n6pilot02. Scientific informativeness is NOT ASSESSABLE,
not evidence of model/algorithm degeneration or absence of risk.

Per authorization, N6_PILOT_REPORT.md and N6_SCIENTIFIC_DIAGNOSIS.md are NOT
rewritten as a full-pilot diagnosis before 80/80. This restart report records the
current stop separately; their historical results are retained. No capacity or
scientific claim is derived from preflight or unit-test timings.

## Audit and decision

docs/evidence/N6_RESTART_STOP.json.gz retains gates, all three raw XML files,
source snapshot/type diagnosis, the launch traceback and zero-run stop facts.
The traceback is transcribed from the captured terminal output with normalized
path display (not presented as a raw stdout/stderr file). Git-object proofs bind
the intended clean execution source; all original evidence remains immutable.
docs/N6_PILOT_HASHES.sha256 excludes itself; final artifact commit/tree are external
anchors, distinct from the intended execution commit. Artifact tests verify the
source proof, gate/XML hashes and tuple/list round-trip cause without any solve.

Stop archive: 16,967 bytes; SHA256
9e95f182c1cd6d06fe6c5427bd2a16fb98c0e4e9668a3862036efa780f2d4f5a.
Four new solver-free stop-artifact tests passed, including a read-only reproduction
of the still-unfixed validator rejection. This is a known blocker regression,
not evidence that the entry is repaired. All final hosted checks are attached to
the artifact commit on PR #8; their success cannot override this observed block.

N6_BLOCKED. Do not enter N7, merge PR #8, retry, or start later runs. A fresh full
batch was authorized, but its failed pre-launch audit now requires external review.
