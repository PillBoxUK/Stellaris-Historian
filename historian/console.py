from __future__ import annotations

from datetime import datetime
from threading import Lock


_PRINT_LOCK = Lock()


def _timestamp() -> str:
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def log(
    message: str,
    *,
    level: str = "INFO",
) -> None:
    """
    Print one clean Historian activity line.

    A lock is used because the save watcher and the web request handlers can
    write to the command window at the same time.
    """
    with _PRINT_LOCK:
        print(
            f"[{_timestamp()}] {level:<7} {message}",
            flush=True,
        )


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
