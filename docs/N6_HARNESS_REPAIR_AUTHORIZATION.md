# N6 authorized harness repair and single diagnostic retry

External review: N6_BLOCKED_CONFIRMED.
Authority: N6_HARNESS_FIX_AUTHORIZED and
N6_SINGLE_DIAGNOSTIC_RETRY_CONDITIONALLY_AUTHORIZED.
N6_FULL_PILOT_RESUME_NOT_AUTHORIZED; N7_NOT_AUTHORIZED.

This addendum records the current user authorization, not a rewrite of the
preregistered N6 protocol/config. Their original bytes/hashes stay fixed.
No N0–N5 scientific implementation, tolerance, solver configuration or A1 rule
may change. The original failed directory/archive stays immutable.

## Fixed engineering repair (before diagnostic results)

Heartbeat reads retry ONLY PermissionError and FileNotFoundError: at most eight
consecutive attempts and at most 0.5 seconds, polling at most every 0.02 seconds.
JSON/schema errors and other exceptions fail immediately. The Windows read handle
permits concurrent atomic rename (FILE_SHARE_READ|WRITE|DELETE); the frozen N1
writer is unchanged. Keep the last valid heartbeat/stage. Use fixed absolute
monotonic deadlines; never reset the current
deadline on a failed read or a repeated stage. Workers carry the original phase
start through later heartbeat updates so delayed observation cannot grant extra
algorithm/postprocess time. Reaching the deadline during a read-conflict window
terminates as incomplete; a normal deadline expiration is time_limit.

Persist exception type/message, errno, winerror, filename/requested path,
traceback, stage, last valid heartbeat, elapsed wall time, true worker exit code
after cleanup, and process-tree cleanup results. Transient conflict windows are
also observable. Cleanup failure never yields success. Preserve all original
failure artifacts; do not reconstruct the old missing traceback retrospectively.

Historic replay must validate source contents against each recorded Git commit
and its exact tree, not the current checkout. A compact Git-object proof supplies
historical objects in shallow CI; every commit/tree/blob object ID is recomputed
before its content is used. The frozen N1 CI file stays unchanged.
A scientific five-method group must still share one source.
Diagnostic retries are explicitly excluded from group pooling.

## One-shot controlled scope

After solver-free tests, real licensed tests and Windows atomic heartbeat stress
tests pass AND their implementation is in a clean commit, run exactly once:

- Parent batch: n6pilot01
- parent_run_id: n6pilot01-00-ef
- New batch: n6diagnostic01
- New run_id: n6diagnostic01-ef-retry
- retry_reason: supervisor heartbeat I/O diagnostic after approved harness repair
- method: EF only
- purpose: harness_diagnostic_only

Derive the complete configuration/binding and unchanged solver settings from the
immutable parent request; verify parent manifest/output and source anchors.
Store cross-batch relative parent path, parent manifest/output SHA, commit/tree,
and embed the parent proof in compact diagnostic evidence. This is not a new
scientific configuration, A0/A1 pair, or capacity measurement.

The CLI has a dedicated diagnostic-retry action and refuses full run/resume.
A locked single-use authorization claim is persisted before spawning the worker,
independent of success/failure; duplicate invocation is rejected even if a new
batch name is proposed. No automatic retry. Stop after this one attempt.

Passing this diagnostic does not complete N6 or authorize N7. Return to the
same Draft PR #7 for external review. A future full rerun would need separate
authorization and a new batch beginning with M0 on a single new clean commit;
never splice old M0/M1 with new EF/A0/A1.
