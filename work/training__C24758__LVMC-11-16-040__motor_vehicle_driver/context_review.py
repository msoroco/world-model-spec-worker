"""Bind independent visibility and exception review to original Native sources."""
import hashlib
import json
import math
from pathlib import Path

from sight_speed_measure import EXPECTED_ID, measure, require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def assemble(attempt, review_path, output):
    attempt = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    review = json.loads(review_path.read_text())
    require(review.get("assignment_id") == EXPECTED_ID, "review assignment mismatch")
    case = review.get("case_id", "")
    require(case in (EXPECTED_ID + "__reference", EXPECTED_ID + "__at_15", EXPECTED_ID + "__contrast"),
            "review case mismatch")
    sources = review.get("source_sha256", {})
    names = ("frame-map.json", "native-ego-readback.jsonl",
             "native-context-readback.json", "native-map-readback.xodr")
    require(set(sources) == set(names), "review source inventory mismatch")
    for name in names:
        require(sha(attempt / name) == sources[name], "review source hash mismatch: " + name)
    context = json.loads((attempt / "native-context-readback.json").read_text())
    require(context.get("assignment_id") == EXPECTED_ID and context.get("case_id") == case,
            "Native context identity mismatch")
    require(context.get("native_map_sha256") == sources["native-map-readback.xodr"],
            "Native map binding mismatch")
    approach_ids = set(context.get("entering_approach_ray_targets", {}))
    require(len(approach_ids) >= 2, "reviewed approaches missing")
    original = [json.loads(line) for line in
                (attempt / "native-ego-readback.jsonl").read_text().splitlines()]
    frame_map = json.loads((attempt / "frame-map.json").read_text())
    reviewed = review.get("frames", [])
    require(len(original) == len(frame_map) == len(reviewed) == 600,
            "review frame count mismatch")
    reviewer = review.get("reviewer", {})
    require(isinstance(reviewer.get("id"), str) and reviewer["id"]
            and isinstance(reviewer.get("method"), str) and reviewer["method"],
            "independent review attribution missing")
    exceptions = review.get("exceptions", {})
    for key in ("through_street", "traffic_controlled_intersection"):
        item = exceptions.get(key, {})
        require(item.get("value") is False and item.get("source") in names
                and item.get("reviewed_by") == reviewer["id"],
                "unresolved exception: " + key)
    rows = []
    boundary_crossed = False
    for i, (raw, mapped, marked) in enumerate(zip(original, frame_map, reviewed)):
        require(raw.get("video_frame") == mapped.get("video_frame") == marked.get("frame") == i
                and raw.get("native_frame") == mapped.get("native_frame") == marked.get("native_frame"),
                "review Native frame join mismatch")
        require(abs(mapped.get("time_s", -1) - i / 20) < 0.0001,
                "review time join mismatch")
        rays = raw.get("original_native_sight_rays")
        require(isinstance(rays, list) and len(rays) == 1 + 3 * len(approach_ids),
                "original sight-ray inventory missing")
        digest = hashlib.sha256(json.dumps(rays, sort_keys=True).encode()).hexdigest()
        require(marked.get("sight_ray_sha256") == digest,
                "review sight-ray binding mismatch")
        require(marked.get("camera_rgb_sha256") == mapped.get("original_rgb_sha256"),
                "review camera-pixel binding mismatch")
        distance = marked.get("distance_to_boundary_m")
        in_junction = raw.get("ego_native_junction_id") == context["junction_id"]
        boundary_crossed = boundary_crossed or in_junction
        require(finite(distance) and (boundary_crossed or distance >= 0),
                "reviewed signed route distance missing")
        if not boundary_crossed:
            require(distance + 0.5 >= raw.get("distance_to_boundary_euclidean_m", float("inf")),
                    "reviewed approach distance geometrically impossible")
        views = marked.get("entering_approach_views")
        require(isinstance(views, dict) and set(views) == approach_ids,
                "review entering approach inventory mismatch")
        require(type(marked.get("intersection_clear_100ft")) is bool,
                "review intersection sight missing")
        for key, view in views.items():
            require(type(view.get("clear_100ft")) is bool
                    and type(view.get("traffic_visible_100ft")) is bool,
                    "review entering sight missing: " + key)
        rows.append({"frame": i, "time_s": i / 20,
                     "distance_to_boundary_m": distance,
                     "ego_speed_mps": raw["ego_speed_mps"],
                     "within_intersection": in_junction,
                     "intersection_clear_100ft": marked["intersection_clear_100ft"],
                     "entering_approach_views": {
                         key: {**views[key],
                               "source_ref": "native-ego-readback.jsonl#" + sources["native-ego-readback.jsonl"]}
                         for key in sorted(approach_ids)}})
    observation = {"assignment_id": EXPECTED_ID,
                   "source_kind": "native_saved_observation", "frame_rate_hz": 20,
                   "entering_approach_ids": sorted(approach_ids),
                   "context": {key: {"value": False,
                                      "source_ref": exceptions[key]["source"] + "#" +
                                      sources[exceptions[key]["source"]]}
                               for key in ("through_street", "traffic_controlled_intersection")},
                   "review_sha256": sha(review_path), "source_sha256": sources,
                   "frames": rows}
    output = Path(output)
    output.write_text(json.dumps(observation, separators=(",", ":")) + "\n")
    return measure(output, sha(output))
