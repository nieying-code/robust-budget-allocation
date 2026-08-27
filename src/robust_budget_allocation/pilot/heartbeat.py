"""Bounded heartbeat reads. Monotonic absolute deadlines never reset on retry."""

import json
import math
import os
import traceback

READ_ATTEMPTS = 8
READ_WINDOW_SECONDS = .5
READ_RETRY_SECONDS = .02
GROUPS = {"startup": "startup", "preflight": "startup", "construction": "startup",
          "algorithm": "algorithm", "verification": "postprocess", "complete": "postprocess"}


def read_text_shared(path):
    """Read a stable file handle without denying an atomic rename on Windows.

    FILE_SHARE_DELETE permits rename while the old handle remains readable.
    https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
    """
    if os.name != "nt":
        return path.read_text(encoding="utf-8")
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = create(str(path), 0x80000000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        exc = ctypes.WinError(ctypes.get_last_error())
        exc.filename = str(path)
        raise exc
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    # open_osfhandle transferred ownership; closing the descriptor closes HANDLE.
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        return stream.read()


def exception_context(exc, *, stage, heartbeat, elapsed, path=None):
    return dict(exception_type=type(exc).__name__, message=str(exc),
                errno=getattr(exc, "errno", None), winerror=getattr(exc, "winerror", None),
                filename=getattr(exc, "filename", None), requested_path=str(path) if path else None,
                traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                stage=stage, last_valid_heartbeat=heartbeat, wall_seconds=elapsed)


class HeartbeatWatch:
    def __init__(self, limits, started):
        if set(limits) != {"startup", "algorithm", "postprocess"} or any(
                not math.isfinite(v) or v <= 0 for v in limits.values()):
            raise ValueError("invalid watchdog limits")
        self.limits, self.started = dict(limits), started
        self.stage, self.last = "startup", None
        self.deadlines = {"startup": started+limits["startup"]}
        self.conflict_start, self.consecutive = None, 0
        self.total_conflicts, self.recovered_windows = 0, 0
        self.errors, self.omitted_errors = [], 0

    @property
    def deadline(self):
        return self.deadlines[self.stage]

    def expired(self, now):
        return now >= self.deadline

    def read(self, path, now):
        """Only read PermissionError/FileNotFoundError are retryable; invalid JSON is fatal."""
        try:
            value = json.loads(read_text_shared(path))
        except (PermissionError, FileNotFoundError) as exc:
            if self.conflict_start is None:
                self.conflict_start = now
            self.consecutive += 1
            self.total_conflicts += 1
            context = exception_context(exc, stage=self.stage, heartbeat=self.last,
                                        elapsed=now-self.started, path=path)
            if len(self.errors) < 64:
                self.errors.append(context)
            else:
                self.omitted_errors += 1
            self.latest_error = context
            return None
        if not isinstance(value, dict) or value.get("stage") not in GROUPS:
            raise ValueError("invalid heartbeat stage/schema")
        group = GROUPS[value["stage"]]
        order = ("startup", "algorithm", "postprocess")
        if order.index(group) < order.index(self.stage):
            raise ValueError("heartbeat stage regression")
        # New workers publish the ORIGINAL group start, not the time of a delayed read.
        # Existing synthetic/legacy heartbeat fixtures without this field use receipt time.
        phase_start = value.get("phase_started_monotonic", now)
        if not isinstance(phase_start, (int, float)) or not math.isfinite(phase_start):
            raise ValueError("invalid heartbeat monotonic phase start")
        # A write may occur during this read; never grant more time than receipt.
        phase_start = min(phase_start, now)
        if group != self.stage:
            if group in self.deadlines:
                raise ValueError("stage deadline cannot restart")
            self.deadlines[group] = phase_start+self.limits[group]
            self.stage = group
        self.last = value
        if self.consecutive:
            self.recovered_windows += 1
        self.consecutive, self.conflict_start = 0, None
        return value

    def conflict_exhausted(self, now):
        return self.consecutive > 0 and (self.consecutive >= READ_ATTEMPTS
            or now-self.conflict_start >= READ_WINDOW_SECONDS or self.expired(now))

    def delay(self, now):
        remaining = max(0., self.deadline-now)
        if self.consecutive:
            return min(READ_RETRY_SECONDS, remaining,
                       max(0., READ_WINDOW_SECONDS-(now-self.conflict_start)))
        return min(.05, remaining)

    def evidence(self):
        return dict(stage=self.stage, last_valid_heartbeat=self.last,
                    absolute_deadlines=self.deadlines, total_read_conflicts=self.total_conflicts,
                    recovered_conflict_windows=self.recovered_windows,
                    consecutive_read_conflicts=self.consecutive, read_errors=self.errors,
                    omitted_read_errors=self.omitted_errors,
                    latest_read_error=getattr(self, "latest_error", None),
                    policy=dict(max_attempts=READ_ATTEMPTS, max_window_seconds=READ_WINDOW_SECONDS,
                                retry_interval_seconds=READ_RETRY_SECONDS))
