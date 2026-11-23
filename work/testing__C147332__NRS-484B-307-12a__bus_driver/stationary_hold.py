"""Independent original-source CPU proof of a green-lane stationary hold."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


SOURCES = ("bus-body-history.jsonl", "trace.jsonl", "controller-history.jsonl",
           "video_frames.jsonl")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("stationary hold needs multiple original frames")
    return rows


def audit(path, *, maximum_drift_m=.15, maximum_speed_mps=.2):
    """Require unchanged full-body position, low measured speed and held brake."""
    path = Path(path)
    acquisition = json.loads((path / "acquisition.json").read_text())
    streams = []
    for name in SOURCES:
        source = path / name
        recorded = acquisition.get(name)
        recorded = recorded.get("sha256") if isinstance(recorded, dict) else recorded
        if not source.is_file() or recorded != _sha(source):
            raise ValueError("stationary original source missing or changed: " + name)
        streams.append(_rows(source))
    bodies, traces, controls, frames = streams
    if len({len(rows) for rows in streams}) != 1:
        raise ValueError("stationary original frame counts differ")
    first_center = None
    largest_drift = 0.0
    for body, trace, control, frame in zip(bodies, traces, controls, frames):
        number = frame.get("carla_frame")
        time = frame.get("time_s")
        if (body.get("frame") != number or trace.get("frame") != number or
                control.get("frame") != number or body.get("elapsed_seconds") != time or
                trace.get("time_s") != time or control.get("elapsed_seconds") != time):
            raise ValueError("stationary original frame/time join differs")
        corners = body.get("bus_footprint")
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError("stationary full bus footprint missing")
        center = [sum(float(v[i]) for v in corners) / 4 for i in (0, 1)]
        if not all(math.isfinite(v) for v in center):
            raise ValueError("stationary body center invalid")
        if first_center is None:
            first_center = center
        largest_drift = max(largest_drift, math.dist(center, first_center))
        position = trace.get("position_m")
        if (not isinstance(position, list) or len(position) < 2 or
                math.dist(center, [float(position[0]), float(position[1])]) > .2):
            raise ValueError("stationary trace/body position differs")
        speed = trace.get("speed_mps")
        if (not isinstance(speed, (int, float)) or isinstance(speed, bool) or
                not math.isfinite(speed) or speed < 0 or speed > maximum_speed_mps):
            raise ValueError("stationary measured speed exceeded bound")
        request = control.get("requested_control", {})
        if (not isinstance(request.get("brake"), (int, float)) or
                request["brake"] < .5 or request.get("throttle", 1) > .01):
            raise ValueError("stationary brake hold missing")
    if largest_drift > maximum_drift_m:
        raise ValueError("stationary full bus body drift exceeded bound")
    return {"status": "stationary_hold_measured", "frames": len(frames),
            "largest_body_drift_m": largest_drift,
            "engineering_maximum_drift_m": maximum_drift_m,
            "engineering_maximum_speed_mps": maximum_speed_mps,
            "source_hashes": {name: _sha(path / name) for name in SOURCES},
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False}
