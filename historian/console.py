from __future__ import annotations

from datetime import datetime
from threading import Lock


_PRINT_LOCK = Lock()
_CURRENT_OPERATION: str | None = None
_CURRENT_OPERATION_ERRORS = 0
_LIVE_HISTORY_CYCLE = False


def _timestamp() -> str:
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _begin_operation(name: str) -> None:
    global _CURRENT_OPERATION, _CURRENT_OPERATION_ERRORS
    _CURRENT_OPERATION = name
    _CURRENT_OPERATION_ERRORS = 0


def _finish_operation() -> None:
    global _CURRENT_OPERATION, _CURRENT_OPERATION_ERRORS

    if _CURRENT_OPERATION is None:
        return

    operation = _CURRENT_OPERATION
    error_count = _CURRENT_OPERATION_ERRORS

    print("", flush=True)
    print("==========================================", flush=True)
    if error_count:
        print("       PROCESS COMPLETED WITH ERRORS", flush=True)
    else:
        print("        ALL UPDATES ARE COMPLETED", flush=True)
    print("==========================================", flush=True)
    print(f"Operation: {operation}", flush=True)
    if error_count:
        print(f"Errors recorded: {error_count}", flush=True)
        print("Check the error lines above before continuing.", flush=True)
    else:
        print("Status: SUCCESS", flush=True)
        print("Historian is ready for the next action.", flush=True)
    print("==========================================", flush=True)
    print("", flush=True)

    _CURRENT_OPERATION = None
    _CURRENT_OPERATION_ERRORS = 0


def _track_before_log(message: str, level: str) -> None:
    global _CURRENT_OPERATION_ERRORS, _LIVE_HISTORY_CYCLE

    if message.startswith("LIVE HISTORY - ") and "archived save(s) waiting" in message:
        _LIVE_HISTORY_CYCLE = True

    if message.startswith("UPDATE HISTORY START - "):
        if not _LIVE_HISTORY_CYCLE:
            _begin_operation("Update History")
    elif message.startswith("REVIEW START - "):
        _begin_operation("Review Campaign")
    elif message.startswith("CONSTRUCT CAMPAIGN START - "):
        _begin_operation("Construct Campaign")

    if level == "ERROR" and _CURRENT_OPERATION is not None:
        _CURRENT_OPERATION_ERRORS += 1


def _track_after_log(message: str, level: str) -> None:
    global _LIVE_HISTORY_CYCLE

    if message.startswith("LIVE HISTORY - Historical_Journal.html refresh complete -"):
        _LIVE_HISTORY_CYCLE = False
        return

    if message.startswith("LIVE HISTORY STOPPED -"):
        _LIVE_HISTORY_CYCLE = False
        return

    if _CURRENT_OPERATION == "Update History":
        if message.startswith("Journal updated - "):
            _finish_operation()
        return

    if _CURRENT_OPERATION == "Review Campaign":
        if message.startswith("REVIEW ABORTED - "):
            _finish_operation()
            return
        if (
            level == "ERROR"
            and "Historical_Journal.html FAILED -" in message
        ):
            _finish_operation()
            return
        if message.startswith("REFRESH COMPLETE - "):
            _finish_operation()
        return

    if _CURRENT_OPERATION == "Construct Campaign":
        if message.startswith("CONSTRUCT CAMPAIGN ABORTED - "):
            _finish_operation()
            return
        if (
            level == "ERROR"
            and "Historical_Journal.html FAILED -" in message
        ):
            _finish_operation()
            return
        if message.startswith("REFRESH COMPLETE - "):
            _finish_operation()


def log(
    message: str,
    *,
    level: str = "INFO",
) -> None:
    """
    Print one clean Historian activity line.

    A lock is used because the save watcher and the web request handlers can
    write to the command window at the same time. v0.0.51 also watches the
    manual Update / Review / Construct workflow markers so the command window
    ends with an unmistakable completion banner after the whole operation is
    actually finished. Automatic Live History cycles are deliberately excluded
    so the banner does not spam during normal play.
    """
    with _PRINT_LOCK:
        _track_before_log(message, level)
        print(
            f"[{_timestamp()}] {level:<7} {message}",
            flush=True,
        )
        _track_after_log(message, level)


def info(message: str) -> None:
    log(
        message,
        level="INFO",
    )


def activity(message: str) -> None:
    log(
        message,
        level="HISTORY",
    )


def archive(message: str) -> None:
    log(
        message,
        level="ARCHIVE",
    )


def warning(message: str) -> None:
    log(
        message,
        level="WARNING",
    )


def error(message: str) -> None:
    log(
        message,
        level="ERROR",
    )


def format_duration(seconds: float) -> str:
    seconds = max(
        0.0,
        float(seconds),
    )

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes, remainder = divmod(
        int(round(seconds)),
        60,
    )

    if minutes < 60:
        return f"{minutes}m {remainder:02d}s"

    hours, minutes = divmod(
        minutes,
        60,
    )

    return f"{hours}h {minutes:02d}m {remainder:02d}s"
