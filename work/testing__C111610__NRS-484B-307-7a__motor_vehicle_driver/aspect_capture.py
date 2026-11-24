"""Acquire original flashing-arrow display samples from an injected Native adapter.

The adapter must read the actual head/display on each world tick. This module
does not infer an arrow aspect from CARLA's coarse traffic-light state.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class AspectError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AspectError(message)


def _inside(root, path):
    root = Path(root).resolve()
    path = Path(path).resolve()
    require(path.is_relative_to(root), "aspect output escapes attempt")
    return path


def validate_rows(rows, site, *, frames=900):
    require(len(rows) == frames and frames >= 3, "aspect frame history incomplete")
    first = rows[0]["frame"]
    states = []
    for i, row in enumerate(rows):
        require(type(row.get("frame")) is int and row["frame"] == first + i,
                "aspect frame continuity failed")
        t = row.get("elapsed_seconds")
        require(type(t) in (float, int) and math.isfinite(t) and
                abs(float(t) - i / 20.0) < 0.002, "aspect 20 Hz time join failed")
        require(str(row.get("head_id")) == str(site["official_head_id"]),
                "official arrow head mismatch")
        require(row.get("facing_approach_id") == site["ego_approach_id"],
                "arrow facing approach mismatch")
        require(row.get("arrow_color") == "yellow" and
                row.get("arrow_direction") == site["arrow_movement"],
                "yellow arrow color or movement missing")
        require(type(row.get("arrow_lit")) is bool, "original arrow on/off readback missing")
        require(row.get("source_kind") in ("display_sensor", "controller_readback", "pixel_decode")
                and isinstance(row.get("source_id"), str) and row["source_id"],
                "original aspect adapter source missing")
        require(row.get("native_head_state") is not None,
                "Native head readback missing")
        indications = row.get("concurrent_indications")
        require(isinstance(indications, list) and
                all(isinstance(v, str) and v for v in indications),
                "concurrent indication inventory missing")
        states.append(row["arrow_lit"])
    transitions = sum(a != b for a, b in zip(states, states[1:]))
    require(any(states) and not all(states) and transitions >= 2,
            "flashing arrow on/off transitions not observed")
    return transitions


def capture(site, attempt_root, readback, *, frames=900, diagnostic=False):
    """Read one source packet per 20 Hz Native tick and seal the original stream.

    `readback(i)` must be called after world tick i and return the adapter's
    original packet. The caller owns world ticking, cameras, actors and cleanup.
    """
    root = Path(attempt_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows = [readback(i) for i in range(frames)]
    require(all(isinstance(row, dict) for row in rows), "aspect source packet missing")
    transitions = validate_rows(rows, site, frames=frames)
    source = _inside(root, root / "arrow-aspect-original.json")
    receipt = _inside(root, root / "arrow-aspect-receipt.json")
    require(not source.exists() and not receipt.exists(), "aspect original already exists")
    encoded = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(len(encoded) <= 2 * 1024 * 1024, "aspect source exceeds return file limit")
    source.write_bytes(encoded)
    doc = {
        "format": "worker-original-arrow-aspect-v1",
        "source_path": source.name,
        "source_sha256": hashlib.sha256(encoded).hexdigest(),
        "frame_count": frames,
        "frequency_hz": 20,
        "first_frame": rows[0]["frame"],
        "head_id": str(site["official_head_id"]),
        "facing_approach_id": site["ego_approach_id"],
        "arrow_direction": site["arrow_movement"],
        "observed_transitions": transitions,
        "diagnostic": bool(diagnostic),
        "physical_acceptance": False,
        "legal_verdict": None,
    }
    receipt.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return doc
