"""Evaluate candidate triggers from saved source measurements, without selection."""
import json
import math
from pathlib import Path


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing trigger source: " + path.name)
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError("Empty trigger source: " + path.name)
    return result


def evaluate(samples_path, route_audit_path, pixel_audit_path, requested_offset_m):
    samples = rows(samples_path)
    route = json.loads(Path(route_audit_path).read_text())
    pixels = json.loads(Path(pixel_audit_path).read_text())
    if route.get("source_kind") != "native_map_readback" or \
       pixels.get("source_kind") != "original_camera_pixels":
        raise ValueError("Trigger audits need declared original-source kinds")
    if not isinstance(route.get("connected_lane_link"), bool):
        raise ValueError("Missing Native lane-link observation")
    approach = [r for r in samples if -35 <= float(r["native_center_xy_m"][0]) <= -10]
    if not approach:
        raise ValueError("No observed approach tracking window")
    errors = [abs(float(r["native_center_xy_m"][1]) - requested_offset_m) for r in approach]
    if not all(math.isfinite(e) for e in errors):
        raise ValueError("Invalid observed tracking error")
    visible = pixels.get("body_and_centerline_visible_frames")
    total = pixels.get("approach_frames")
    if type(visible) is not int or type(total) is not int or total < 1 or not 0 <= visible <= total:
        raise ValueError("Invalid original pixel audit counts")
    completed = route.get("full_body_destination_exit_observed_by_24s")
    if not isinstance(completed, bool):
        raise ValueError("Missing full-body exit observation")
    return {"fallback1": not route["connected_lane_link"] or not completed,
            "fallback2": max(errors) > 0.35,
            "fallback3": visible / total < 0.95,
            "metrics": {"maximum_approach_tracking_error_m": max(errors),
                        "approach_pixel_visible_fraction": visible / total,
                        "connected_lane_link": route["connected_lane_link"],
                        "full_body_destination_exit_observed_by_24s": completed},
            "scope": "Source-based trigger logic only; CPU fixture values do not establish CARLA observations"}
