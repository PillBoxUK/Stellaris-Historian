from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Config:
    save_root: Path
    host: str
    port: int
    recent_campaign_limit: int
    open_browser: bool
    poll_seconds: float
    stable_seconds: float


def load_config(base_dir: Path) -> Config:
    raw = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))

    return Config(
        save_root=Path(raw["save_root"]),
        host=str(raw.get("host", "127.0.0.1")),
        port=int(raw.get("port", 8766)),
        recent_campaign_limit=max(1, int(raw.get("recent_campaign_limit", 5))),
        open_browser=bool(raw.get("open_browser", True)),
        poll_seconds=max(0.5, float(raw.get("poll_seconds", 2.0))),
        stable_seconds=max(1.0, float(raw.get("stable_seconds", 3.0))),
    )
