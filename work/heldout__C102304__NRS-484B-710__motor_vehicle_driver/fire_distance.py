"""Measured native footprint separation for NRS 484B.710 preparation.

Inputs are ordered horizontal footprints from the original Native frame, in
metres. This module does not infer alarm purpose, following intent, parking,
vehicle authorization, or a legal verdict from positions.
"""

from __future__ import annotations

from math import hypot, isfinite
from hashlib import sha256
import json
from pathlib import Path

from shapely.geometry import Polygon

FEET_PER_METRE = 3.280839895013123
BOUNDARY_FEET = 500.0


def _polygon(vertices, name):
    if len(vertices) != 4:
        raise ValueError(f"{name} requires four ordered measured ground corners")
    points = []
    for vertex in vertices:
        if len(vertex) != 2 or any(not isfinite(float(v)) for v in vertex):
            raise ValueError(f"{name} contains invalid ground coordinates")
        points.append(tuple(float(v) for v in vertex))
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError(f"{name} is not a valid full footprint")
    return polygon


def measure_frame(ego_corners, apparatus_corners):
    """Return actual nearest body gap and a separate centre diagnostic."""
    ego = _polygon(ego_corners, "ego")
    apparatus = _polygon(apparatus_corners, "apparatus")
    body_m = ego.distance(apparatus)
    centre_m = hypot(ego.centroid.x - apparatus.centroid.x,
                     ego.centroid.y - apparatus.centroid.y)
    return {
        "nearest_footprint_gap_m": body_m,
        "nearest_footprint_gap_ft": body_m * FEET_PER_METRE,
        "centre_distance_m": centre_m,
        "centre_distance_ft": centre_m * FEET_PER_METRE,
        "overlap_or_contact": body_m == 0,
    }


def measure_history(samples, expected_frames):
    """Preserve every original tick; reject gaps and identity substitutions.

    Each sample must carry original Native frame/time, stable participant IDs,
    and ordered measured footprints. The caller must separately bind provenance
    to the source file and decide which frames satisfy a statutory branch.
    """
    if len(samples) != expected_frames or expected_frames <= 0:
        raise ValueError("Incomplete original Native frame history")
    output = []
    identities = None
    previous_frame = None
    previous_time = None
    for sample in samples:
        frame = sample.get("frame")
        time_s = sample.get("time_s")
        ids = (sample.get("ego_id"), sample.get("apparatus_id"))
        if (isinstance(frame, bool) or not isinstance(frame, int)
                or isinstance(time_s, bool) or not isinstance(time_s, (int, float))
                or not isfinite(time_s) or not all(ids) or ids[0] == ids[1]):
            raise ValueError("Invalid Native frame identity or time")
        if identities is not None and ids != identities:
            raise ValueError("Participant identity changed")
        if previous_frame is not None and (frame != previous_frame + 1 or time_s <= previous_time):
            raise ValueError("Missing or unordered Native frame")
        try:
            measured = measure_frame(sample["ego_corners"], sample["apparatus_corners"])
        except (KeyError, TypeError) as error:
            raise ValueError("Missing measured Native footprint") from error
        output.append({"frame": frame, "time_s": time_s, **measured})
        identities = ids
        previous_frame = frame
        previous_time = time_s
    return output


def measure_native_source(source_path, expected_frames):
    """Read retained Native JSONL, never a fixture-only derived channel."""
    source_path = Path(source_path)
    raw = source_path.read_bytes()
    if not raw:
        raise ValueError("Empty retained Native participant source")
    try:
        samples = [json.loads(line) for line in raw.splitlines()]
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Invalid retained Native JSONL") from error
    history = measure_history(samples, expected_frames)
    return {
        "source_sha256": sha256(raw).hexdigest(),
        "source_path": str(source_path),
        "frame_count": len(history),
        "measurements": history,
    }
