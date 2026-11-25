"""Source-bound original-footprint audit for the C125763 yield-sign crossing.

The yield sign's governance and subsection-4 qualification are retained as
reviewed context. Timing and body overlap are measurements, never legal findings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C125763__NRS-484B-250-1__motor_vehicle_driver"
SOURCES = ("road.xodr", "site-context.json", "ego-body-history.jsonl",
           "other-body-history.jsonl", "original-device-source.txt",
           "original-highway-source.txt")


def need(ok, text):
    if not ok:
        raise ValueError(text)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def polygon(vertices):
    need(isinstance(vertices, list) and len(vertices) >= 3, "missing original polygon")
    need(all(isinstance(p, list) and len(p) == 2 and all(number(x) for x in p)
             for p in vertices), "invalid original polygon vertex")
    points = [(float(x), float(y)) for x, y in vertices]
    signs = []
    for i in range(len(points)):
        a, b, c = (points[(i+j) % len(points)] for j in range(3))
        cross = (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
        need(abs(cross) > 1e-10, "degenerate original polygon")
        signs.append(cross > 0)
    need(all(x == signs[0] for x in signs), "nonconvex original polygon")
    return points


def overlap(body, region):
    for points in (body, region):
        for i, a in enumerate(points):
            b = points[(i+1) % len(points)]
            axis = (a[1]-b[1], b[0]-a[0])
            bp = [axis[0]*p[0]+axis[1]*p[1] for p in body]
            rp = [axis[0]*p[0]+axis[1]*p[1] for p in region]
            if max(bp) < min(rp) or max(rp) < min(bp):
                return False
    return True


def source(root, manifest, name):
    path = root/name
    binding = manifest.get(name)
    need(path.is_file() and not path.is_symlink() and isinstance(binding, dict)
         and binding.get("kind") == "original_native" and binding.get("sha256") == sha(path),
         "missing or stale original Native source: " + name)
    return path


def history(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    need(len(lines) >= 3 and all(line.strip() for line in lines),
         "complete original Native history required: " + path.name)
    return [json.loads(line) for line in lines]


def transitions(rows, region, actor):
    state = [overlap(polygon(row.get("body_vertices_xy_m")), region) for row in rows]
    need(not state[0], actor + ": history begins after entry")
    first_entry = next((i for i in range(1, len(state)) if state[i] and not state[i-1]), None)
    need(first_entry is not None, actor + ": no original entry")
    first_exit = next((i for i in range(first_entry+1, len(state)) if not state[i] and state[i-1]), None)
    need(first_exit is not None, actor + ": original exit not captured")
    need(not any(state[first_exit:]), actor + ": original body reentered intersection")
    def bracket(index):
        return {"lower_frame": rows[index-1]["frame"], "upper_frame": rows[index]["frame"],
                "lower_time_s": rows[index-1]["time_s"], "upper_time_s": rows[index]["time_s"]}
    return bracket(first_entry), bracket(first_exit), state


def measure(attempt):
    root = Path(attempt)
    need(root.is_dir() and not root.is_symlink(), "saved attempt directory required")
    manifest_path = root/"source-manifest.json"
    need(manifest_path.is_file() and not manifest_path.is_symlink(), "source manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = {name: source(root, manifest, name) for name in SOURCES}
    site = json.loads(files["site-context.json"].read_text(encoding="utf-8"))
    need(site.get("assignment_id") == ASSIGNMENT and site.get("cell_id") == "C125763",
         "saved assignment/cell identity differs")
    need(site.get("map_sha256") == sha(files["road.xodr"]), "reviewed site map differs")
    for key, retained in (("device_source", "original-device-source.txt"),
                          ("highway_source", "original-highway-source.txt")):
        binding = site.get(key)
        need(isinstance(binding, dict) and binding.get("citation") and
             binding.get("sha256") == sha(files[retained]),
             "reviewed original device/highway source differs: " + key)
    need(site.get("review_status") in ("diagnostic_fixture", "reviewed_original"),
         "original site review status missing")
    for key in ("reviewer", "map_source_citation", "highway_source_citation",
                "device_source_citation", "crossing_id", "roadway_id"):
        need(isinstance(site.get(key), str) and site[key], "missing reviewed context: " + key)
    need(site.get("ego_highway") != site.get("other_highway") and
         all(isinstance(site.get(k), str) and site[k] for k in ("ego_highway", "other_highway")),
         "different highways not established")
    need(site.get("approach_relation") == "crossing", "opposite-approach exception unresolved")
    need(site.get("ego_side") in ("left", "right") and
         site.get("other_side") in ("left", "right") and
         site["ego_side"] != site["other_side"], "relative approaches missing")
    need(site.get("official_yield_sign_present") is True, "C125763 yield-sign identity missing")
    need(type(site.get("yield_sign_controls_intersection")) is bool,
         "official-device governance missing")
    need(type(site.get("subsection_4_reviewed")) is bool,
         "subsection-4 qualification review status missing")
    need(type(site.get("ego_actor_id")) is int and type(site.get("other_actor_id")) is int
         and site["ego_actor_id"] != site["other_actor_id"], "two distinct actors required")
    region = polygon(site.get("intersection_polygon_xy_m"))
    ego = history(files["ego-body-history.jsonl"])
    other = history(files["other-body-history.jsonl"])
    need(len(ego) == len(other), "original histories differ in length")
    previous = None
    for a, b in zip(ego, other):
        frame, time = a.get("frame"), a.get("time_s")
        need((frame, time) == (b.get("frame"), b.get("time_s")),
             "original frame/time join differs")
        need(a.get("actor_id") == site["ego_actor_id"] and
             b.get("actor_id") == site["other_actor_id"], "original actor identity differs")
        need(type(frame) is int and number(time), "invalid original frame/time")
        if previous:
            need(frame == previous[0]+1 and 0.049 <= time-previous[1] <= 0.051,
                 "original 20 Hz frame sequence differs")
        previous = frame, time
    ego_entry, ego_exit, ego_state = transitions(ego, region, "ego")
    other_entry, other_exit, other_state = transitions(other, region, "other")
    overlap_frames = [ego[i]["frame"] for i in range(len(ego)) if ego_state[i] and other_state[i]]
    return {"format": "worker-c125763-original-crossing-v1", "assignment_id": ASSIGNMENT,
            "case_id": site.get("case_id"), "crossing_id": site["crossing_id"],
            "roadway_id": site["roadway_id"], "ego_entry": ego_entry,
            "other_entry": other_entry, "ego_exit": ego_exit, "other_exit": other_exit,
            "other_entered_before_ego": other_entry["upper_frame"] < ego_entry["upper_frame"],
            "other_cleared_before_ego_entry": other_exit["upper_frame"] <= ego_entry["upper_frame"],
            "simultaneous_body_overlap_frames": overlap_frames,
            "yield_sign_controls_intersection": site["yield_sign_controls_intersection"],
            "subsection_4_reviewed": site["subsection_4_reviewed"],
            "ego_side": site["ego_side"], "other_side": site["other_side"],
            "original_frame_count": len(ego),
            "source_sha256": {name: manifest[name]["sha256"] for name in SOURCES},
            "legal_applicability": "unresolved_subsection_4_and_device_exception",
            "legal_verdict_claimed": False}


def compare(left, right):
    need(all(x.get("format") == "worker-c125763-original-crossing-v1" and
             x.get("assignment_id") == ASSIGNMENT and x.get("source_sha256")
             for x in (left, right)), "source-bound exact measurements required")
    need(left.get("case_id") != right.get("case_id") and
         all(x.get("case_id") for x in (left, right)), "two exact case identities required")
    for field in ("crossing_id", "roadway_id", "other_entry", "other_exit",
                  "yield_sign_controls_intersection", "subsection_4_reviewed",
                  "ego_side", "other_side", "original_frame_count"):
        need(left.get(field) == right.get(field), "fixed comparison condition changed: " + field)
    need(left.get("other_entered_before_ego") and right.get("other_entered_before_ego"),
         "other-first entry is required in both exact cases")
    need(left.get("other_cleared_before_ego_entry") !=
         right.get("other_cleared_before_ego_entry"),
         "ego response did not change measured clearance order")
    return {"format": "worker-c125763-comparison-audit-v1",
            "case_ids": [left["case_id"], right["case_id"]],
            "declared_difference": "ego_response_clearance_order",
            "source_sha256": [left["source_sha256"], right["source_sha256"]],
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
