from __future__ import annotations

from pathlib import Path
from threading import Event, Lock, Thread
import hashlib
import os
import shutil
import time

from .console import archive, error, info
from .db import Database
from .save_reader import read_campaign_summary, valid_stellaris_save


def _sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


class CampaignWatcher:
    def __init__(
        self,
        db: Database,
        archive_root: Path,
        poll_seconds: float,
        stable_seconds: float,
    ):
        self.db = db
        self.archive_root = archive_root
        self.poll_seconds = poll_seconds
        self.stable_seconds = stable_seconds

        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None

        self._selected_path: Path | None = None
        self._campaign_id: int | None = None

        self._candidate_signature: tuple[float, int] | None = None
        self._candidate_since: float | None = None
        self._processed_signature: tuple[float, int] | None = None

        self.status = "Waiting for campaign"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = Thread(
            target=self._run,
            name="stellaris-historian-watcher",
            daemon=True,
        )
        self._thread.start()
        info(
            "Save watcher started."
        )

    def stop(self) -> None:
        self._stop.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        info(
            "Save watcher stopped."
        )

    def select_campaign(self, save_path: Path, campaign_id: int) -> None:
        with self._lock:
            self._selected_path = save_path.resolve()
            self._campaign_id = campaign_id
            self._candidate_signature = None
            self._candidate_since = None
            self._processed_signature = None
            self.status = "Monitoring selected campaign"

        campaign = self.db.campaign(
            campaign_id
        )

        label = (
            campaign["empire_name"]
            if campaign is not None
            else save_path.parent.name
        )

        info(
            f"Monitoring selected campaign: {label}"
        )

    def clear_campaign(self) -> None:
        with self._lock:
            self._selected_path = None
            self._campaign_id = None
            self._candidate_signature = None
            self._candidate_since = None
            self._processed_signature = None
            self.status = "Waiting for campaign"

        info("Campaign monitoring cleared - waiting for campaign selection.")

    def selected(self) -> tuple[Path | None, int | None]:
        with self._lock:
            return self._selected_path, self._campaign_id

    def _stable_and_new(self, path: Path) -> bool:
        stat = path.stat()
        signature = (stat.st_mtime, stat.st_size)

        if signature == self._processed_signature:
            return False

        now = time.monotonic()

        if signature != self._candidate_signature:
            self._candidate_signature = signature
            self._candidate_since = now
            return False

        if self._candidate_since is None:
            self._candidate_since = now
            return False

        if now - self._candidate_since < self.stable_seconds:
            return False

        return valid_stellaris_save(path)

    def _copy_verified(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.unlink(missing_ok=True)

        before = source.stat()
        shutil.copy2(source, temporary)
        after = source.stat()

        if (
            before.st_mtime != after.st_mtime
            or before.st_size != after.st_size
        ):
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Save changed while it was being copied.")

        if not valid_stellaris_save(temporary):
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Copied save did not validate correctly.")

        os.replace(temporary, destination)

    def _capture(self, path: Path, campaign_id: int) -> None:
        summary = read_campaign_summary(path)
        digest = _sha256(path)
        stat = path.stat()

        if self.db.snapshot_hash_exists(campaign_id, digest):
            self._processed_signature = (stat.st_mtime, stat.st_size)
            self.status = (
                f"Monitoring - {summary.empire_name} "
                f"{summary.game_date} already archived"
            )

            archive(
                f"{summary.game_date} already archived - no duplicate copy made."
            )

            return

        campaign = self.db.campaign(campaign_id)

        if campaign is None:
            raise RuntimeError("Campaign record no longer exists.")

        count = self.db.snapshot_count(campaign_id)

        if count == 0:
            kind = "start"
            sequence = None
            filename = "ironman-start.sav"
        else:
            kind = "periodic"
            sequence = self.db.next_sequence(campaign_id)
            filename = f"ironman-{sequence}.sav"

        destination = Path(campaign["archive_dir"]) / filename
        self._copy_verified(path, destination)

        self.db.insert_snapshot(
            campaign_id,
            sequence_no=sequence,
            kind=kind,
            game_date=summary.game_date,
            sha256=digest,
            archive_filename=filename,
            archive_path=str(destination),
            source_mtime=stat.st_mtime,
            source_size=stat.st_size,
        )

        self.db.update_campaign(
            campaign_id,
            empire_name=summary.empire_name,
            game_version=summary.version,
            game_date=summary.game_date,
        )

        self._processed_signature = (stat.st_mtime, stat.st_size)

        self.status = (
            f"Monitoring - archived {filename} "
            f"at {summary.game_date}"
        )

        size_mb = (
            stat.st_size
            / (1024 * 1024)
        )

        archive(
            f"Captured {filename} - {summary.game_date} - {size_mb:.2f} MB"
        )

    def _run(self) -> None:
        self.archive_root.mkdir(parents=True, exist_ok=True)

        while not self._stop.is_set():
            path, campaign_id = self.selected()

            if path is None or campaign_id is None:
                self.status = "Waiting for campaign"
                self._stop.wait(self.poll_seconds)
                continue

            if not path.exists():
                self.status = "Selected ironman.sav is missing"
                self._stop.wait(self.poll_seconds)
                continue

            try:
                if self._stable_and_new(path):
                    self._capture(path, campaign_id)
            except Exception as exc:
                self.status = f"Monitoring error: {exc}"

                error(
                    f"WATCHER - {exc}"
                )

            self._stop.wait(self.poll_seconds)

        self.status = "Stopped"
