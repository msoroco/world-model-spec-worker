"""CPU-only construction and source-bound measurement for the selected branch.

Longitudinal coordinates increase toward the intersection. This module produces
engineering observations; it does not decide statutory compliance or the
incorporated rules governing the right to proceed after a stop.
"""

from dataclasses import dataclass
from math import hypot, isfinite


@dataclass(frozen=True)
class Site:
    approach_id: str
    official_device_id: str
    governed_approach_id: str
    crosswalk_entry_m: float | None
    limit_line_m: float | None
    intersection_entry_m: float
    occluder_corners_m: tuple[tuple[float, float], ...]
    heavy_vehicle_length_m: float
    heavy_vehicle_width_m: float
    lane_width_m: float


def stop_reference(site: Site) -> tuple[str, float]:
    """Select a documented fixture alternative, not a legal priority rule."""
    if not site.approach_id or not site.official_device_id:
        raise ValueError("missing governed official signal identity")
    if site.governed_approach_id != site.approach_id:
        raise ValueError("signal does not govern this approach")
    if site.heavy_vehicle_length_m <= 0 or site.heavy_vehicle_width_m <= 0:
        raise ValueError("missing heavy vehicle dimensions")
    if site.heavy_vehicle_width_m >= site.lane_width_m:
        raise ValueError("heavy vehicle cannot fit in selected lane")
    if len(site.occluder_corners_m) != 4:
        raise ValueError("blind approach needs constructed occluder polygon")
    if not all(isfinite(v) for corner in site.occluder_corners_m for v in corner):
        raise ValueError("invalid occluder coordinate")
    if site.crosswalk_entry_m is not None:
        return "crosswalk", site.crosswalk_entry_m
    if site.limit_line_m is not None:
        return "limit_line", site.limit_line_m
    return "intersection", site.intersection_entry_m


def occluded(eye: tuple[float, float], target: tuple[float, float],
             polygon: tuple[tuple[float, float], ...]) -> bool:
    """Segment intersection with an axis-aligned rectangular occluder."""
    if len(polygon) != 4:
        raise ValueError("four occluder corners required")
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    if min(xs) == max(xs) or min(ys) == max(ys):
        raise ValueError("zero-area occluder")
    if set(polygon) != {(x, y) for x in (min(xs), max(xs)) for y in (min(ys), max(ys))}:
        raise ValueError("occluder must be an axis-aligned rectangle")
    dx, dy = target[0] - eye[0], target[1] - eye[1]
    lo, hi = 0.0, 1.0
    for origin, delta, lower, upper in ((eye[0], dx, min(xs), max(xs)),
                                        (eye[1], dy, min(ys), max(ys))):
        if delta == 0:
            if origin < lower or origin > upper:
                return False
        else:
            a, b = (lower - origin) / delta, (upper - origin) / delta
            lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
            if lo > hi:
                return False
    return lo < hi and hi > 0 and lo < 1


def measure(site: Site, frames: list[dict]) -> dict:
    """Require original frame and signal sources; report stop before reference."""
    kind, reference = stop_reference(site)
    if len(frames) < 3:
        raise ValueError("insufficient original frames for flash and stop")
    required = {"original_frame", "time_s", "front_m", "speed_mps", "red_lit",
                "signal_id", "approach_id", "source_ref"}
    if any(required - frame.keys() for frame in frames):
        raise ValueError("missing original motion or signal source")
    if any(not frame["source_ref"] for frame in frames):
        raise ValueError("missing source reference")
    if any(frame["signal_id"] != site.official_device_id or
           frame["approach_id"] != site.approach_id for frame in frames):
        raise ValueError("signal or approach source mismatch")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("original frame order is not monotone")
    if any(not isfinite(frame["front_m"]) or not isfinite(frame["speed_mps"]) or
           frame["speed_mps"] < 0 for frame in frames):
        raise ValueError("invalid motion sample")
    transitions = sum(frames[i]["red_lit"] != frames[i + 1]["red_lit"]
                      for i in range(len(frames) - 1))
    if transitions < 2 or not any(frame["red_lit"] for frame in frames):
        raise ValueError("intermittent red illumination not established")
    stopped = [frame for frame in frames if frame["speed_mps"] == 0]
    return {
        "reference_kind": kind,
        "reference_m": reference,
        "flash_transitions": transitions,
        "stopped_before_reference": any(frame["front_m"] < reference for frame in stopped),
        "stop_original_frames": [frame["original_frame"] for frame in stopped],
        "source_refs": list(dict.fromkeys(frame["source_ref"] for frame in frames)),
        "post_stop_rules": "unresolved",
    }
