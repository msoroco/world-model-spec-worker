"""Full-duration synthetic exercise of the original-source entry-order audit."""
import json
import shutil
from pathlib import Path

from comparison_audit import audit_entry_order

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime-work/c125714-entry-order-comparison-v1"
FRAMES = 1100


def body(x, y):
    return [[x - 1, y - 1], [x + 1, y - 1], [x + 1, y + 1], [x - 1, y + 1]]


def make_source(path, other_entry):
    path.mkdir(parents=True, exist_ok=True)
    context = {
        "native_map_id": "synthetic-median-map", "intersection_id": 5,
        "ego_highway_id": 1, "other_highway_id": 2,
        "ego_road_id": 11, "other_road_id": 22,
        "crossing_geometry_source": "synthetic-polygon",
        "all_entrances_source": "synthetic-two-road-inventory",
        "official_device_inventory_source": "synthetic-empty-inventory",
        "median_spacing_source": "synthetic-fixed-spacing",
        "same_statutory_crossing": True,
        "official_device_controls_crossing": False,
        "opposite_approach_with_left_turn": False,
        "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "diagnostic_only": True,
    }
    (path / "junction_context.json").write_text(json.dumps(context) + "\n")
    with (path / "crossing_history.jsonl").open("w") as history, (path / "video_frames.jsonl").open("w") as video:
        for i in range(FRAMES):
            frame, time = 1000 + i, i / 20
            row = {"frame": frame, "time_s": time,
                   "ego_vertices_m": body(5 if i >= 360 else -4, 5),
                   "ego": {"intersection_id": 5, "road_id": 11,
                           "body_vertices_xy_m": body(5 if i >= 360 else -4, 5)},
                   "other": {"intersection_id": 5, "road_id": 22,
                             "body_vertices_xy_m": body(5 if i >= other_entry else 14, 5)}}
            history.write(json.dumps(row) + "\n")
            video.write(json.dumps({"video_frame": i, "carla_frame": frame, "time_s": time}) + "\n")


if __name__ == "__main__":
    if OUT.exists():
        shutil.rmtree(OUT)
    left, right = OUT / "other_first", OUT / "other_later"
    make_source(left, 300)
    make_source(right, 420)
    proof = audit_entry_order(left, right, FRAMES)
    assert proof["left_other_enters_before_ego"] is True
    assert proof["right_other_enters_before_ego"] is False
    assert proof["left_other_inside_at_ego_entry"] is True
    assert proof["right_other_inside_at_ego_entry"] is False
    context_path = right / "junction_context.json"
    original = context_path.read_text()
    changed = json.loads(original)
    changed["median_spacing_source"] = "changed-synthetic-spacing"
    context_path.write_text(json.dumps(changed) + "\n")
    try:
        try:
            audit_entry_order(left, right, FRAMES)
        except ValueError as exc:
            assert "median_spacing_source" in str(exc), str(exc)
        else:
            raise AssertionError("Changed fixed crossing condition was accepted")
    finally:
        context_path.write_text(original)
    print(json.dumps({"format": proof["format"], "frames": FRAMES,
                      "left_sources": proof["left_sources"], "right_sources": proof["right_sources"],
                      "negative": "changed_median_spacing_source_rejected",
                      "software_comparison_passed": True,
                      "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}))
