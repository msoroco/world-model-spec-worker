"""Full-duration synthetic proof of the opposite-left-turn comparison auditor."""
import hashlib
import json
import shutil
from pathlib import Path

from turn_exception_audit import MODES, audit_trio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime-work/c125714-opposite-turn-v1"
FRAMES = 1100


def body(x, y):
    return [[x - 1, y - 1], [x + 1, y - 1], [x + 1, y + 1], [x - 1, y + 1]]


def make_source(path, mode):
    path.mkdir(parents=True, exist_ok=True)
    intent = mode != "straight"
    context = {
        "native_map_id": "synthetic-opposite-map", "intersection_id": 5,
        "ego_highway_id": 1, "other_highway_id": 2,
        "ego_road_id": 11, "other_road_id": 22,
        "crossing_geometry_source": "synthetic-polygon",
        "all_entrances_source": "synthetic-road-inventory",
        "official_device_inventory_source": "synthetic-empty-device-inventory",
        "median_spacing_source": "synthetic-fixed-median",
        "same_statutory_crossing": True,
        "official_device_controls_crossing": False,
        "opposite_approach": True,
        "opposite_approach_source": "synthetic-initial-headings",
        "opposite_approach_with_left_turn": intent,
        "camera_plan_sha256": hashlib.sha256(b"synthetic-fixed-four-camera-plan").hexdigest(),
        "approach_geometry_source": "synthetic-fixed-approaches",
        "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "diagnostic_only": True,
    }
    (path / "junction_context.json").write_text(json.dumps(context) + "\n")
    route_source = path / "authored_route.txt"
    route_source.write_text("synthetic other " + mode + " route\n")
    route = {"ego_actor_id": 1, "other_actor_id": 2,
             "ego_turn_intent": "straight",
             "other_turn_intent": "straight" if mode == "straight" else "left",
             "route_plan_source": {"path": route_source.name,
                                   "sha256": hashlib.sha256(route_source.read_bytes()).hexdigest()}}
    (path / "route_intent.json").write_text(json.dumps(route) + "\n")
    with (path / "crossing_history.jsonl").open("w") as history, (path / "video_frames.jsonl").open("w") as video:
        for i in range(FRAMES):
            fraction = min(1.0, max(0.0, (i - 300) / 200)) if mode == "makes_left" else 0.0
            other_x = 14 if i < 300 else 5
            other_y = 5 - 9 * fraction
            ego_x = -4 if i < 360 else 5
            other_heading = 180 + 90 * fraction
            frame, time = 1000 + i, i / 20
            row = {"frame": frame, "time_s": time,
                   "ego_vertices_m": body(ego_x, 5),
                   "ego": {"actor_id": 1, "intersection_id": 5, "road_id": 11,
                           "heading_deg": 0, "body_vertices_xy_m": body(ego_x, 5)},
                   "other": {"actor_id": 2, "intersection_id": 5, "road_id": 22,
                             "heading_deg": other_heading,
                             "body_vertices_xy_m": body(other_x, other_y)}}
            history.write(json.dumps(row) + "\n")
            video.write(json.dumps({"video_frame": i, "carla_frame": frame,
                                    "time_s": time}) + "\n")


if __name__ == "__main__":
    if OUT.exists():
        shutil.rmtree(OUT)
    roots = {mode: OUT / mode for mode in MODES}
    for mode in MODES:
        make_source(roots[mode], mode)
    proof = audit_trio(roots, FRAMES)
    assert proof["software_comparison_passed"] is True
    assert proof["cases"]["straight"]["subsection_1_exception_active"] is False
    assert all(proof["cases"][mode]["subsection_1_exception_active"] is True
               for mode in MODES[1:])
    context_path = roots["intends_left"] / "junction_context.json"
    original = context_path.read_text()
    changed = json.loads(original)
    changed["opposite_approach_with_left_turn"] = False
    context_path.write_text(json.dumps(changed) + "\n")
    try:
        try:
            audit_trio(roots, FRAMES)
        except ValueError as error:
            assert "Declared left-turn exception differs" in str(error), str(error)
        else:
            raise AssertionError("False declared exception accepted")
    finally:
        context_path.write_text(original)
    route_source = roots["makes_left"] / "authored_route.txt"
    original = route_source.read_text()
    route_source.write_text("changed synthetic route\n")
    try:
        try:
            audit_trio(roots, FRAMES)
        except ValueError as error:
            assert "Authored route-plan source changed" in str(error), str(error)
        else:
            raise AssertionError("Changed route source accepted")
    finally:
        route_source.write_text(original)
    print(json.dumps({"format": proof["format"], "expected_frames": FRAMES,
                      "modes": {mode: {"sources": proof["cases"][mode]["sources"],
                                       "heading_change_deg": proof["cases"][mode]["other_heading_change_deg"],
                                       "exception_active": proof["cases"][mode]["subsection_1_exception_active"]}
                                for mode in MODES},
                      "negative_proofs": ["false_declared_exception", "changed_route_plan_source"],
                      "software_comparison_passed": True,
                      "physical_acceptance_claimed": False,
                      "legal_conclusion": "unresolved"}))
