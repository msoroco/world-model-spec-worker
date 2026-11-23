"""Write a Native-speed source once from observed frame samples.

Call this from the eventual CARLA runner after retaining the original frame map.
It does not choose targets, invent observations, or connect to CARLA on import.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from speed_boundary import EXPECTED_FRAMES, EXPECTED_HZ


def write_original_speed(attempt: Path, case_id: str, native_run_id: str,
                         samples: list[dict], *, diagnostic_fixture: bool = False) -> dict:
    if not case_id or not native_run_id or type(diagnostic_fixture) is not bool:
        raise ValueError("missing original speed identity")
    if len(samples) != EXPECTED_FRAMES:
        raise ValueError("original speed needs 900 frames")
    origin = samples[0].get("frame")
    if not isinstance(origin, int) or isinstance(origin, bool) or origin < 0:
        raise ValueError("invalid original frame origin")
    rows = []
    for index, sample in enumerate(samples):
        if set(sample) != {"frame", "time_s", "speed_mps", "speed_uncertainty_mps"}:
            raise ValueError("original speed sample fields differ")
        if sample["frame"] != origin + index:
            raise ValueError("original speed frame sequence differs")
        for name in ("time_s", "speed_mps", "speed_uncertainty_mps"):
            value = sample[name]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError("invalid original " + name)
        if abs(sample["time_s"] - index / EXPECTED_HZ) > 1e-6:
            raise ValueError("original speed sample time differs")
        if sample["speed_mps"] < 0 or sample["speed_uncertainty_mps"] < 0:
            raise ValueError("negative original speed or uncertainty")
        rows.append(sample)
    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    source = attempt / "original-speed.jsonl"
    descriptor_path = attempt / "speed-source.json"
    if source.exists() or descriptor_path.exists():
        raise ValueError("original speed source already exists")
    raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    descriptor = {
        "format": "c10301-original-speed-source-v1", "case_id": case_id,
        "source": source.name, "sha256": hashlib.sha256(raw).hexdigest(),
        "sample_rate_hz": EXPECTED_HZ, "sample_count": EXPECTED_FRAMES,
        "source_frame_origin": origin, "native_run_id": native_run_id,
        "diagnostic_fixture": diagnostic_fixture,
    }
    source.write_bytes(raw)
    descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n")
    return descriptor
