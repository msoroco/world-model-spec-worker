"""Original-frame intersection sight and traversal-speed measurement.

The ray rows are measurements from the declared virtual observer. A clear ray
through a capped range is censored, not a claim about farther traffic. Unknown
or missing incoming arms remain unknown rather than being treated as clear.
"""

from __future__ import annotations

import hashlib
import json
from math import isfinite

from sight_construction import FEET_100_M, MPH_15_MPS


class MeasurementError(ValueError):
    pass


def evaluate(packet: dict) -> dict:
    needed = ("case_id", "map_hash", "site_source_sha256", "boundary_source_sha256",
              "through_source_sha256", "control_source_sha256", "entering_arms",
              "frames", "frame_source_sha256", "ray_source_sha256", "speed_source_sha256")
    if any(not packet.get(k) for k in needed):
        raise MeasurementError("original source or site binding absent")
    arms = packet["entering_arms"]
    if not isinstance(arms, list) or len(arms) < 3 or len(set(arms)) != len(arms):
        raise MeasurementError("entering arm inventory incomplete")
    frames = packet["frames"]
    if len(frames) < 2:
        raise MeasurementError("insufficient original samples")
    ids = [f["frame"] for f in frames]
    if any(b != a + 1 for a, b in zip(ids, ids[1:])):
        raise MeasurementError("non-contiguous original frame identities")
    times = [f["time_s"] for f in frames]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise MeasurementError("non-monotone original timestamps")
    approaching = []
    crossing = []
    for f in frames:
        distance = f.get("approach_distance_m")
        speed = f.get("ego_speed_mps")
        if not isinstance(distance, (float, int)) or not isfinite(distance):
            raise MeasurementError("measured approach distance missing")
        if not isinstance(speed, (float, int)) or not isfinite(speed) or speed < 0:
            raise MeasurementError("original ego speed missing")
        if 0 <= distance <= FEET_100_M:
            rays = f.get("rays")
            if not isinstance(rays, dict) or set(rays) != set(arms):
                raise MeasurementError("every entering arm needs a ray packet per approach frame")
            for arm in arms:
                r = rays[arm]
                if r.get("observer_convention") not in (
                    "lane_waypoint_1.4m_bbox_9", "ego_reference_1.4m_arm_rays"
                ):
                    raise MeasurementError("undeclared observer convention")
                if r.get("sampled_extent_m", 0) < FEET_100_M:
                    raise MeasurementError("100-foot arm extent not sampled")
                if r.get("intersection_view") not in ("clear", "blocked"):
                    raise MeasurementError("intersection view unknown")
                if r.get("traffic_view") not in ("clear", "blocked"):
                    raise MeasurementError("traffic view unknown")
                if not r.get("ray_frame_source_sha256"):
                    raise MeasurementError("ray-to-frame source binding missing")
                if r.get("observer_convention") == "ego_reference_1.4m_arm_rays":
                    trace = r.get("ray_hit_trace")
                    if (not isinstance(trace, dict) or trace.get("frame") != f["frame"] or
                            trace.get("arm") != arm or
                            not isinstance(trace.get("census"), dict)):
                        raise MeasurementError("original ray hit trace or census missing")
                    def digest(value):
                        return hashlib.sha256(json.dumps(value, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                    if digest(trace) != r["ray_frame_source_sha256"]:
                        raise MeasurementError("original ray hit trace hash mismatch")
                    census = dict(trace["census"])
                    sealed = census.pop("source_sha256", None)
                    if (sealed != digest(census) or census.get("frame") != f["frame"] or
                            census.get("arm") != arm or
                            census.get("source_kind") != "original_native_actor_census"):
                        raise MeasurementError("original traffic census seal mismatch")
            approaching.append(f)
        if f.get("traversing_intersection") is True:
            crossing.append(f)
    if not approaching or approaching[0]["approach_distance_m"] < FEET_100_M - 1:
        raise MeasurementError("last 100-foot approach not covered")
    if approaching[-1]["approach_distance_m"] > 1:
        raise MeasurementError("approach missing intersection boundary")
    if not crossing:
        raise MeasurementError("no measured traversal frames")
    blocked = [(f["frame"], arm, aspect) for f in approaching for arm in arms
               for aspect in ("intersection_view", "traffic_view")
               if f["rays"][arm][aspect] == "blocked"]
    speeds = [f["ego_speed_mps"] for f in crossing]
    return {
        "case_id": packet["case_id"], "map_hash": packet["map_hash"],
        "approach_frame_ids": [f["frame"] for f in approaching],
        "traversal_frame_ids": [f["frame"] for f in crossing],
        "blocked_rays": blocked, "all_views_clear": len(blocked) == 0,
        "traversal_speed_min_mps": min(speeds), "traversal_speed_max_mps": max(speeds),
        "prima_facie_value_mps": MPH_15_MPS,
        "above_15_mph_observed": any(v > MPH_15_MPS for v in speeds),
        "through_designation": packet.get("through_designation"),
        "traffic_controlled": packet.get("traffic_controlled"),
        "source_sha256": {k: packet[k] for k in needed if k.endswith("_sha256")},
        "legal_conclusion": None,
    }


def compare(a: dict, b: dict, changed: set[str]) -> None:
    """Independent pair check; does not decide legal compliance."""
    required = ("map_hash", "approach_frame_ids", "traversal_frame_ids",
                "blocked_rays", "through_designation", "traffic_controlled",
                "traversal_speed_min_mps", "traversal_speed_max_mps", "source_sha256")
    if any(k not in a or k not in b for k in required):
        raise MeasurementError("comparison evidence missing")
    if a["map_hash"] != b["map_hash"]:
        raise MeasurementError("comparison map differs")
    for key in ("through_designation", "traffic_controlled"):
        if key not in changed and a[key] != b[key]:
            raise MeasurementError(f"fixed {key} changed")
    if "sight" not in changed and a["blocked_rays"] != b["blocked_rays"]:
        raise MeasurementError("fixed sight condition changed")
    if "sight" in changed and a["blocked_rays"] == b["blocked_rays"]:
        raise MeasurementError("declared sight contrast not measured")
    if "traversal_speed" not in changed and (
        a["traversal_speed_min_mps"], a["traversal_speed_max_mps"]
    ) != (b["traversal_speed_min_mps"], b["traversal_speed_max_mps"]):
        raise MeasurementError("fixed traversal speed changed")
    if "traversal_speed" in changed and (
        a["traversal_speed_min_mps"], a["traversal_speed_max_mps"]
    ) == (b["traversal_speed_min_mps"], b["traversal_speed_max_mps"]):
        raise MeasurementError("declared traversal-speed contrast not measured")
    for key in ("through_designation", "traffic_controlled"):
        if key in changed and a[key] == b[key]:
            raise MeasurementError(f"declared {key} contrast not measured")
    if not changed.intersection({"sight", "through_designation", "traffic_controlled", "traversal_speed"}):
        raise MeasurementError("no declared difference")
