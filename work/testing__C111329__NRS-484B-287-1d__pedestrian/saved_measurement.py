"""Independent original-frame crossing measurement; no legality evaluator."""
from __future__ import annotations

import math

from native_crossing import crossing_plan, digest, point
from native_acquisition import CAMERAS, _sha


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def inside_polygon(p, polygon):
    x, y = point(p)
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(_cross(a, b, (x, y))) < 1e-9 and min(a[0], b[0]) <= x <= max(a[0], b[0]) and min(a[1], b[1]) <= y <= max(a[1], b[1]):
            return False
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1]) + a[0]:
            inside = not inside
    return inside


def measure(plan: dict, frames: list[dict], device_observations: list[dict]) -> dict:
    """Require original continuous frames, observed walker and device readback."""
    if len(frames) < 3 or not device_observations:
        raise ValueError("original walker and device histories required")
    indexes = [f["original_frame"] for f in frames]
    if any(b != a + 1 for a, b in zip(indexes, indexes[1:])):
        raise ValueError("noncontiguous original frames")
    ids = {f.get("walker_id") for f in frames}
    if None in ids or len(ids) != 1:
        raise ValueError("walker identity discontinuity")
    polygon = [point(p) for p in plan["intersection_polygon"]]
    actual = [point(f["walker_center_xy"]) for f in frames]
    if math.dist(actual[0], point(plan["start"])) > 1.5 or math.dist(actual[-1], point(plan["end"])) > 1.5:
        raise ValueError("crossing endpoints not observed")
    if not any(inside_polygon(p, polygon) for p in actual):
        raise ValueError("no intersection traversal observed")
    by_frame = {d["original_frame"]: d for d in device_observations}
    if any(i not in by_frame for i in indexes):
        raise ValueError("device history incomplete")
    if any(not by_frame[i].get("source_sha256") or not by_frame[i].get("official_source") for i in indexes):
        raise ValueError("official device source missing")
    authorized = all(by_frame[i].get("pedestrian_governance") == "diagonal" and by_frame[i].get("state") == "permissive" for i in indexes if inside_polygon(actual[indexes.index(i)], polygon))
    return {"original_frame_start": indexes[0], "original_frame_end": indexes[-1], "walker_id": next(iter(ids)), "observed_start_xy": actual[0], "observed_end_xy": actual[-1], "observed_inside_frames": sum(inside_polygon(p, polygon) for p in actual), "authorization_observed_during_inside": authorized, "device_source_hashes": sorted({by_frame[i]["source_sha256"] for i in indexes}), "route_kind_planned": plan["route_kind"], "exception_484B_290": "unresolved"}


def measure_acquisition(site: dict, packet: dict, *, case_id: str,
                        route_kind: str, authorization: bool,
                        expected_frames: int = 900, allow_diagnostic: bool = False) -> dict:
    """Saved-only join of the immutable site, Native rows and device history.

    A diagnostic packet is accepted only for explicit CPU fixture tests. The
    return is a physical observation summary, never a legal conclusion.
    """
    if packet.get("format") != "crossing-native-acquisition-v1" or packet.get("case_id") != case_id:
        raise ValueError("exact case Native acquisition mismatch")
    if packet.get("diagnostic") is not False and not allow_diagnostic:
        raise ValueError("diagnostic Native acquisition rejected for delivery")
    plan = crossing_plan(site, route_kind, authorization)
    if packet.get("site_sha256") != digest(site) or packet.get("plan_sha256") != _sha(plan):
        raise ValueError("saved site or route source hash mismatch")
    rows = packet.get("rows")
    if not isinstance(rows, list) or len(rows) != expected_frames or packet.get("frame_count") != expected_frames or packet.get("rows_sha256") != _sha(rows):
        raise ValueError("original Native rows missing or unsealed")
    if packet.get("fps") != 20 or packet.get("original_frame_start") != rows[0].get("original_frame") or packet.get("original_frame_end") != rows[-1].get("original_frame"):
        raise ValueError("original Native frame contract mismatch")
    device_ids = {d["id"] for d in site["devices"]}
    times = []
    walker_frames = []
    device_frames = []
    for row in rows:
        frame = row["original_frame"]
        times.append(row["elapsed_seconds"])
        if set(row.get("camera_frames", {})) != set(CAMERAS) or any(row["camera_frames"][name] != frame for name in CAMERAS):
            raise ValueError("saved four-camera original frame mismatch")
        devices = row.get("devices", [])
        if len(devices) != len(device_ids) or {d.get("id") for d in devices} != device_ids:
            raise ValueError("saved device inventory incomplete")
        for d in devices:
            original = next(item for item in site["devices"] if item["id"] == d["id"])
            if d.get("official_source") != original["official_source"] or d.get("instruction_source") != original["instruction_source"] or d.get("pedestrian_governance") != original.get("pedestrian_governance"):
                raise ValueError("saved device source changed")
            if not isinstance(d.get("source_sha256"), str) or len(d["source_sha256"]) != 64:
                raise ValueError("saved device readback source missing")
        chosen = next((d for d in devices if d["id"] in plan["authorizing_device_ids"]), devices[0])
        walker_frames.append({"original_frame": frame, "walker_id": row["walker_id"], "walker_center_xy": row["walker_center_xy"]})
        device_frames.append({"original_frame": frame, "source_sha256": chosen["source_sha256"],
                              "official_source": chosen["official_source"],
                              "pedestrian_governance": chosen["pedestrian_governance"], "state": chosen["state"]})
    if any(not math.isfinite(t) for t in times) or any(abs((b - a) - 0.05) > 0.002 for a, b in zip(times, times[1:])):
        raise ValueError("saved Native time discontinuity")
    result = measure(plan, walker_frames, device_frames)
    result.update({"case_id": case_id, "site_sha256": packet["site_sha256"],
                   "native_rows_sha256": packet["rows_sha256"],
                   "camera_frames_verified": True, "diagnostic": packet.get("diagnostic")})
    return result
