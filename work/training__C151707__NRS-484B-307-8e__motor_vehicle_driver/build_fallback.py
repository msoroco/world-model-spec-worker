"""Construct slower steering fallback for a measurable route tracking failure."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for suffix, primary in (("probe_01", ROOT / "native/cases/probe_01/construction.json"),
                        ("probe_02", ROOT / "construction.json")):
    construction = json.loads(primary.read_text())
    runner = next(f for f in construction["files"] if f["path"] == "runner.py")
    old = "target_speed = 4.0 if distance > 3 else 2.0"
    new = "target_speed = 2.0 if distance > 3 else 1.0"
    if runner["content"].count(old) != 1:
        raise ValueError("Control speed source changed")
    runner["content"] = runner["content"].replace(old, new)
    construction["mechanisms"]["fallback_control"] = "Half-speed waypoint approach for an observed route cross-track failure"
    path = ROOT / "native" / "fallbacks" / suffix / "construction.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(construction, indent=2, sort_keys=True) + "\n")
    print(suffix, str(path.relative_to(ROOT)), sha(path))
