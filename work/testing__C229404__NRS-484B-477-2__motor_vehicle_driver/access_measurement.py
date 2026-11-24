"""Measure original alley parking footprint against abutting-property access.

Polygon overlap is an engineering observation. The statutory word "block" is
left for source review; no overlap area or clearance is made a legal cutoff.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229404__NRS-484B-477-2__motor_vehicle_driver"
SOURCE_NAMES = ("frame_map", "alley_geometry", "vehicle_footprint", "activity")


def _load_source(root: Path, entry: dict) -> dict:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("original source path escapes attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original alley source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("original alley source hash mismatch")
    return json.loads(raw)


def _polygon(raw: object, name: str) -> list[tuple[float, float]]:
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError(f"{name} polygon absent")
    points = []
    for point in raw:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in point)):
            raise ValueError(f"{name} polygon point invalid")
        points.append((float(point[0]), float(point[1])))
    if len(set(points)) != len(points):
        raise ValueError(f"{name} polygon repeats a point")
    if _signed_area(points) < 0:
        points.reverse()
    if abs(_signed_area(points)) < 1e-9:
        raise ValueError(f"{name} polygon has no area")
    signs = []
    for i in range(len(points)):
        a, b, c = points[i - 1], points[i], points[(i + 1) % len(points)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-9:
            signs.append(cross > 0)
    if not signs or len(set(signs)) != 1:
        raise ValueError(f"{name} polygon must be convex")
    return points


def _signed_area(points: list[tuple[float, float]]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(points, points[1:] + points[:1])) / 2


def _overlap_area(subject: list[tuple[float, float]],
                  clip: list[tuple[float, float]]) -> float:
    """Convex polygon intersection via half-plane clipping, in square metres."""
    result = subject
    for a, b in zip(clip, clip[1:] + clip[:1]):
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

        def intersection(p, q):
            sp, sq = side(p), side(q)
            fraction = sp / (sp - sq)
            return (p[0] + fraction * (q[0] - p[0]),
                    p[1] + fraction * (q[1] - p[1]))

        previous = result
        result = []
        if not previous:
            break
        for p, q in zip(previous[-1:] + previous[:-1], previous):
            inside_p, inside_q = side(p) >= -1e-10, side(q) >= -1e-10
            if inside_p != inside_q:
                result.append(intersection(p, q))
            if inside_q:
                result.append(q)
    return abs(_signed_area(result)) if len(result) >= 3 else 0.0


def measure(root: Path, inventory: dict, case_id: str) -> dict:
    root = Path(root)
    if not case_id.startswith(ASSIGNMENT + "__") or inventory.get("case_id") != case_id:
        raise ValueError("exact parking case mismatch")
    if inventory.get("source_kind") != "original_native":
        raise ValueError("original Native source required")
    sources = inventory.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_NAMES):
        raise ValueError("complete original alley source inventory required")
    packets = {name: _load_source(root, sources[name]) for name in SOURCE_NAMES}
    geometry = packets["alley_geometry"]
    if (geometry.get("source_kind") != "original_native_geometry" or
            geometry.get("highway_status") is not True or
            geometry.get("cul_de_sac") is not False or
            not geometry.get("highway_source") or
            not geometry.get("alley_classification_source") or
            not geometry.get("cul_de_sac_source") or
            not geometry.get("property_abutting_source") or
            not geometry.get("property_id") or
            not geometry.get("driveway_ownership_source") or
            not geometry.get("vehicular_use_source")):
        raise ValueError("qualifying alley and abutting driveway provenance incomplete")
    access = _polygon(geometry.get("access_corridor_polygon_m"), "access corridor")
    if geometry.get("access_kind") not in ("driveway", "entrance"):
        raise ValueError("access kind must be driveway or entrance")
    frames = packets["frame_map"].get("frames")
    if not isinstance(frames, list) or len(frames) < 900:
        raise ValueError("original 900-frame history missing")
    first = frames[0].get("frame")
    if type(first) is not int or [r.get("frame") for r in frames] != list(range(first, first + len(frames))):
        raise ValueError("original frames not consecutive")
    times = [r.get("time_s") for r in frames]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or any(
            abs(b - a - .05) > .005 for a, b in zip(times, times[1:])):
        raise ValueError("original frame clock not 20 Hz")
    body = packets["vehicle_footprint"]
    activity = packets["activity"]
    for name, packet in (("vehicle footprint", body), ("activity", activity)):
        if packet.get("case_id") != case_id or packet.get("source_kind") != "original_native":
            raise ValueError(f"{name} original identity mismatch")
        if not isinstance(packet.get("samples"), list) or len(packet["samples"]) != len(frames):
            raise ValueError(f"{name} original history incomplete")
    measured = []
    for frame, b, state in zip(frames, body["samples"], activity["samples"]):
        for name, row in (("vehicle footprint", b), ("activity", state)):
            if row.get("frame") != frame["frame"] or row.get("time_s") != frame["time_s"]:
                raise ValueError(f"{name} frame/time join mismatch")
        if b.get("vehicle_id") != geometry.get("ego_vehicle_id"):
            raise ValueError("original body vehicle identity mismatch")
        footprint = _polygon(b.get("polygon_m"), "vehicle footprint")
        if state.get("state") not in ("approaching", "stopping", "standing", "parked", "departing"):
            raise ValueError("actual stopping/standing/parking activity missing")
        if type(state.get("speed_mps")) not in (int, float) or state["speed_mps"] < 0:
            raise ValueError("original speed invalid")
        if state["state"] in ("standing", "parked") and state["speed_mps"] > .1:
            raise ValueError("stationary phase speed inconsistent")
        if state["state"] in ("stopping", "standing", "parked"):
            measured.append({"frame": frame["frame"], "time_s": frame["time_s"],
                             "state": state["state"],
                             "access_intrusion_area_m2": round(_overlap_area(footprint, access), 8)})
    if not any(row["state"] == "parked" for row in measured):
        raise ValueError("actual parked phase absent")
    return {"format": "c229404-original-access-measurement-v1", "case_id": case_id,
            "source_sha256": {name: sources[name]["sha256"] for name in SOURCE_NAMES},
            "original_frames": len(frames), "measured_halt_frames": len(measured),
            "access_kind": geometry["access_kind"], "property_id": geometry["property_id"],
            "max_access_intrusion_area_m2": max(r["access_intrusion_area_m2"] for r in measured),
            "halt_samples": measured, "statutory_blocking_judgment": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite original access measurement")
    inventory = json.loads((args.attempt / "inventory.json").read_text())
    result = measure(args.attempt, inventory, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
