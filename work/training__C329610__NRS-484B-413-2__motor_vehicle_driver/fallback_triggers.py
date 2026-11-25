"""Source-bound CPU evaluator for three C329610 signal-package fallback risks."""
import hashlib
import json
import math
from pathlib import Path


def evaluate(samples: Path, *, expected_sha256: str, source_kind: str, map_sha256: str) -> dict:
    if source_kind not in ("synthetic_cpu_fixture", "original_native_capture"):
        raise ValueError("source kind is not an observed capture")
    if len(map_sha256) != 64:
        raise ValueError("map identity missing")
    raw = samples.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("source hash mismatch")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != 800 or any(r.get("frame") != i or r.get("time_s") != i / 20 for i, r in enumerate(rows)):
        raise ValueError("incomplete source interval")
    turns = [i for i, r in enumerate(rows) if r.get("course_change")]
    if len(turns) != 1 or not 1 < turns[0] < len(rows) - 1:
        raise ValueError("course change source missing")
    turn = turns[0]
    onset = next((i for i, r in enumerate(rows[:turn+1]) if r.get("signal") == "left"), None)
    if onset is None or not all(r.get("signal") == "left" for r in rows[onset:turn+1]):
        raise ValueError("continuous signal source missing")
    window = rows[onset:turn+1]
    errors = [r.get("route_error_m") for r in window]
    visible = [r.get("signal_visible") for r in window]
    if any(type(e) not in (int, float) or not math.isfinite(e) or e < 0 for e in errors):
        raise ValueError("original tracking metric missing")
    if any(type(v) is not bool for v in visible):
        raise ValueError("camera review metric missing")
    margin = rows[onset]["ego_xy_m"][0] - rows[0]["ego_xy_m"][0]
    maximum = max(errors)
    fraction = sum(visible) / len(visible)
    return {"source_sha256": digest, "map_sha256": map_sha256, "source_kind": source_kind,
            "runway_to_signal_onset_m": margin, "max_signal_window_route_error_m": maximum,
            "signal_visibility_fraction": fraction,
            "fallback1": margin < 12.0, "fallback2": maximum > .35, "fallback3": fraction < .95,
            "dispatchable_observation": False,
            "limitations": ["synthetic source does not prove original Native behavior",
                            "visibility is a source annotation requiring independent pixel review"]}
