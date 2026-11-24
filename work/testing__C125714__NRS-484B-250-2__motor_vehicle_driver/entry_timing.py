"""Original-source crossing entry measurement for C125714 and NRS 484B.250(2).

This is a measurement and comparison audit, not an applicability or legal verdict.
All geometry and context must be reviewed against the original Native map later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver"
SOURCES = ("road.xodr", "site-context.json", "ego-body-history.jsonl", "other-body-history.jsonl")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root: Path, manifest: dict, name: str) -> Path:
    path = root / name
    binding = manifest.get(name)
    require(path.is_file() and not path.is_symlink() and isinstance(binding, dict)
            and binding.get("kind") == "original_native" and binding.get("sha256") == sha(path),
            "missing or stale original Native source: " + name)
    return path


def finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def polygon(value) -> list[tuple[float, float]]:
    require(isinstance(value, list) and len(value) >= 3, "missing body/intersection polygon")
    require(all(isinstance(p, list) and len(p) == 2 and all(finite_number(v) for v in p)
                for p in value), "invalid polygon coordinate")
    points = [(float(x), float(y)) for x, y in value]
    signs = []
    for i in range(len(points)):
        a, b, c = (points[(i + j) % len(points)] for j in range(3))
        cross = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
        require(abs(cross) > 1e-10, "degenerate polygon edge")
        signs.append(cross > 0)
    require(all(sign == signs[0] for sign in signs), "nonconvex original polygon")
    return points


def intersects(first: list[tuple[float, float]], second: list[tuple[float, float]]) -> bool:
    """Inclusive separating-axis test; footprint contact counts as entry."""
    for poly in (first, second):
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            axis = (a[1] - b[1], b[0] - a[0])
            q = [axis[0]*p[0] + axis[1]*p[1] for p in first]
            r = [axis[0]*p[0] + axis[1]*p[1] for p in second]
            if max(q) < min(r) or max(r) < min(q):
                return False
    return True


def rows(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= 3 and all(line.strip() for line in lines),
            "complete original Native body history required: " + path.name)
    result = [json.loads(line) for line in lines]
    require(all(isinstance(row, dict) for row in result), "invalid Native history row")
    return result


def first_entry(history: list[dict], region: list[tuple[float, float]], actor: str) -> dict:
    previous = None
    for row in history:
        inside = intersects(polygon(row.get("body_vertices_xy_m")), region)
        if inside:
            require(previous is not None, actor + ": initial frame already intersects intersection")
            return {"lower_frame": previous["frame"], "upper_frame": row["frame"],
                    "lower_time_s": previous["time_s"], "upper_time_s": row["time_s"]}
        previous = row
    raise ValueError(actor + ": no original body entry transition")


def measure(attempt: Path) -> dict:
    attempt = Path(attempt)
    require(attempt.is_dir() and not attempt.is_symlink(), "saved attempt directory required")
    manifest_path = attempt / "source-manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "source manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = {name: source(attempt, manifest, name) for name in SOURCES}
    site = json.loads(files["site-context.json"].read_text(encoding="utf-8"))
    require(site.get("assignment_id") == ASSIGNMENT and site.get("cell_id") == "C125714",
            "wrong saved assignment or cell")
    require(site.get("map_sha256") == sha(files["road.xodr"]), "Native map differs from site review")
    for key in ("reviewer", "map_source_citation", "highway_source_citation",
                "device_source_citation", "crossing_id", "roadway_id"):
        require(isinstance(site.get(key), str) and site[key], "missing reviewed site context: " + key)
    require(site.get("ego_actor_id") != site.get("other_actor_id")
            and all(type(site.get(k)) is int for k in ("ego_actor_id", "other_actor_id")),
            "two distinct original vehicle identities required")
    require(all(isinstance(site.get(k), str) and site[k] for k in
                ("ego_highway", "other_highway")), "highway identities required")
    require(site.get("approach_relation") in ("crossing", "opposite"), "approach relation missing")
    if site["approach_relation"] == "crossing":
        require(site["ego_highway"] != site["other_highway"],
                "different highways required for crossing branch")
        require(site.get("ego_side") in ("left", "right") and
                site.get("other_side") in ("left", "right") and
                site["ego_side"] != site["other_side"], "relative left/right approaches missing")
    else:
        require(site["ego_highway"] == site["other_highway"],
                "opposite approaches require common highway identity")
    require(type(site.get("official_device_controls_intersection")) is bool,
            "official device governance is unresolved")
    require(type(site.get("other_left_turn_intent")) is bool,
            "left-turn intent requires source-reviewed declaration")
    require(type(site.get("subsection_4_context_reviewed")) is bool,
            "subsection 4 qualification review missing")
    region = polygon(site.get("intersection_polygon_xy_m"))
    ego = rows(files["ego-body-history.jsonl"])
    other = rows(files["other-body-history.jsonl"])
    require(len(ego) == len(other), "original actor histories have unequal frame counts")
    previous = None
    for a, b in zip(ego, other):
        frame, time = a.get("frame"), a.get("time_s")
        require((frame, time) == (b.get("frame"), b.get("time_s")),
                "original frame/time join differs")
        require(a.get("actor_id") == site["ego_actor_id"] and
                b.get("actor_id") == site["other_actor_id"], "original actor identity differs")
        require(type(frame) is int and finite_number(time), "invalid original frame/time")
        if previous is not None:
            require(frame == previous[0]+1 and 0.049 <= time-previous[1] <= 0.051,
                    "original 20 Hz frame sequence has gap or time reversal")
        polygon(a.get("body_vertices_xy_m"))
        polygon(b.get("body_vertices_xy_m"))
        previous = frame, time
    e = first_entry(ego, region, "ego")
    o = first_entry(other, region, "other")
    delta = e["upper_time_s"] - o["upper_time_s"]
    return {"format": "worker-c125714-entry-timing-v1", "assignment_id": ASSIGNMENT,
            "case_id": site.get("case_id"), "crossing_id": site["crossing_id"],
            "roadway_id": site["roadway_id"], "ego_entry": e, "other_entry": o,
            "intersection_entry_time_difference_s": delta,
            "difference_bracket_s": [e["lower_time_s"]-o["upper_time_s"],
                                     e["upper_time_s"]-o["lower_time_s"]],
            "ego_side": site["ego_side"], "other_side": site["other_side"],
            "approach_relation": site["approach_relation"],
            "official_device_controls_intersection": site["official_device_controls_intersection"],
            "other_left_turn_intent": site["other_left_turn_intent"],
            "subsection_4_context_reviewed": site["subsection_4_context_reviewed"],
            "original_frame_count": len(ego),
            "source_sha256": {name: manifest[name]["sha256"] for name in SOURCES},
            "legal_applicability": "unresolved_review", "approximately_same_time": "unresolved_judgment",
            "legal_verdict_claimed": False}


def compare(left: dict, right: dict, variable: str) -> dict:
    require(variable in ("entry_timing", "ego_side", "official_device_governance"),
            "unsupported comparison variable")
    require(all(item.get("format") == "worker-c125714-entry-timing-v1" and
                item.get("assignment_id") == ASSIGNMENT and item.get("source_sha256")
                for item in (left, right)), "source-bound measurements required")
    require(left.get("case_id") != right.get("case_id") and
            all(item.get("case_id") for item in (left, right)), "distinct exact cases required")
    fixed = ("crossing_id", "roadway_id", "approach_relation", "other_left_turn_intent",
             "subsection_4_context_reviewed", "original_frame_count")
    for key in fixed:
        require(left.get(key) == right.get(key), "fixed condition changed: " + key)
    expected = {"entry_timing": "intersection_entry_time_difference_s",
                "ego_side": "ego_side",
                "official_device_governance": "official_device_controls_intersection"}[variable]
    for key in ("intersection_entry_time_difference_s", "ego_side",
                "other_side", "official_device_controls_intersection"):
        if key != expected and not (variable == "ego_side" and key == "other_side"):
            require(left.get(key) == right.get(key), "undeclared difference: " + key)
    require(left.get(expected) != right.get(expected), "declared comparison variable did not differ")
    if variable == "ego_side":
        require(left.get("other_side") != right.get("other_side"),
                "other approach side failed to reverse")
    return {"format": "worker-c125714-comparison-audit-v1", "case_ids": [left["case_id"],
            right["case_id"]], "variable": variable,
            "source_sha256": [left["source_sha256"], right["source_sha256"]],
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
