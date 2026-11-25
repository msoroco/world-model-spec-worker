"""Build nine-frame source-shaped software diagnostics for four timing cases.

The Core graph scaffold is the runtime's generic converter example. Its
telemetry is never used as the C125697 statutory measurement source.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.fixture_generator import generate

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def packed(value):
    return json.dumps(value, sort_keys=True) + "\n"


def body(x, y):
    return [[x - .2, y - .2], [x + .2, y - .2],
            [x + .2, y + .2], [x - .2, y + .2]]


SUFFIXES = ("timing_below_training", "timing_inside_training",
            "timing_above_training", "right_approach_inside")


def build(suffix):
    if suffix not in SUFFIXES:
        raise ValueError("unknown exact timing case")
    case = ROOT.name + "__" + suffix
    planned = next(row for row in json.loads((ROOT / "case-plan.json").read_text())["cases"]
                   if row["case_id"] == case)
    spec = copy.deepcopy(json.loads((REPO / "runtime/fixtures/example.json").read_text()))
    files = spec["files"]
    name = "inspected diagnostic map"
    map_bytes = name.encode()
    scene = {
        "case_id": case,
        "law_id": "NRS-484B-250-2", "cell_id": "C125697",
        "actor": "motor_vehicle_driver", "requested_entry_offset_s": planned["planned_entry_time_difference_s"],
        "crossing": {"id": "median-crossing-diagnostic", "kind": "median_opening_roadway_crossing",
                     "bounds_xy_m": [-2, -2, 2, 2],
                     "opendrive_sha256": hashlib.sha256(map_bytes).hexdigest()},
        "ego_highway": "north-south", "other_highway": "east-west",
        "highway_identity_source": "diagnostic highway source",
        "public_access_source": "diagnostic highway source",
        "device_inventory_source": "diagnostic device source",
        "governing_signal": {"kind": "official_traffic_signal", "readback_state": "inoperative",
                             "controls_traffic": False, "controlled_approach_road_ids": [1, 2]},
        "ego_approach_road_id": 1, "other_approach_road_id": 2,
        "ego_blueprint": "vehicle.car.ego", "other_blueprint": "vehicle.car.other",
        "ego_route_xy_m": [[0, -10], [0, 0], [0, 10]],
        "other_route_xy_m": [[-10, 0], [0, 0], [10, 0]],
        "subsection_4_applicability_review": "unresolved diagnostic context",
        "opposing_left_turn_excluded_source": "unresolved diagnostic context",
        "ego_movement": "straight", "other_movement": "straight",
        "ego_approach_side": "left", "other_approach_side": "right",
    }
    if suffix == "right_approach_inside":
        for key in ("highway", "approach_road_id", "route_xy_m", "approach_side"):
            left, right = "ego_" + key, "other_" + key
            scene[left], scene[right] = scene[right], scene[left]
    rows = [json.loads(s) for s in files["video_frames.jsonl"].splitlines()]
    if len(rows) != 9:
        raise ValueError("runtime diagnostic scaffold frame count changed")
    ego_entry, other_entry = {
        "timing_below_training": (1, 5), "timing_inside_training": (3, 3),
        "timing_above_training": (6, 1), "right_approach_inside": (3, 3),
    }[suffix]
    frames = []
    for index, mapped in enumerate(rows):
        ego_y = -10 if index < ego_entry else 0
        other_x = -10 if index < other_entry else (0 if index < other_entry + 2 else 10)
        if suffix == "right_approach_inside":
            ego_x = -10 if index < ego_entry else 0
            other_y = -10 if index < other_entry else (
                0 if index < other_entry + 2 else 10)
            ego_body, other_body = body(ego_x, 0), body(0, other_y)
        else:
            ego_body, other_body = body(0, ego_y), body(other_x, 0)
        frames.append({"frame": index, "time_s": index / 20,
                       "native_frame_id": mapped["carla_frame"],
                       "native_elapsed_seconds": mapped["time_s"],
                       "signal_readback": "inoperative",
                       "ego": {"id": 10, "road_id": scene["ego_approach_road_id"],
                               "body_vertices_xy_m": ego_body},
                       "other": {"id": 11, "road_id": scene["other_approach_road_id"],
                                 "body_vertices_xy_m": other_body}})
    trace = {"case_id": case, "map_sha256": scene["crossing"]["opendrive_sha256"],
             "actor_ids": {"ego": 10, "other": 11}, "frames": frames}
    files["scene.json"] = packed(scene)
    files["crossing_geometry.json"] = packed({
        "intersection_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
        "source_opendrive_sha256": scene["crossing"]["opendrive_sha256"],
        "crossing_id": scene["crossing"]["id"],
        "legal_judgment": "unresolved"})
    files["native_trace.json"] = packed(trace)
    files["crossing_history.jsonl"] = "".join(json.dumps({
        "frame": row["native_frame_id"],
        "time_s": row["native_elapsed_seconds"],
        "ego_vertices_m": row["ego"]["body_vertices_xy_m"]}) + "\n"
        for row in frames)
    files["opendrive.xodr"] = name
    files["device_inventory.json"] = packed({"source": "diagnostic only", "signal": "inoperative"})
    files["highway_identity.json"] = packed({"ego_highway": scene["ego_highway"],
                                              "other_highway": scene["other_highway"],
                                              "public_access_confirmed": True,
                                              "source": "diagnostic only"})
    files["fixture-provenance.json"] = packed({
        "scope": "CPU software diagnostic only; no physical or legal acceptance",
        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        "frames": 9, "case_id": case})
    core_manifest = json.loads(files["capture/manifest.json"])
    core_manifest["case_id"] = case
    files["capture/manifest.json"] = packed(core_manifest)
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c125697-video-") as temporary:
        temporary = Path(temporary)
        generate({"files": {}, "graphs": [], "videos": spec["videos"]}, temporary)
        paths = {"native_trace": "native_trace.json", "opendrive": "opendrive.xodr",
                 "device_inventory": "device_inventory.json",
                 "highway_identity": "highway_identity.json"}
        paths.update({"camera_" + name: name + ".mkv" for name in CAMERAS})
        sources = {}
        for key, path in paths.items():
            data = (temporary / path).read_bytes() if key.startswith("camera_") else files[path].encode()
            sources[key] = {"path": path, "sha256": hashlib.sha256(data).hexdigest()}
    files["original-source-manifest.json"] = packed({
        "case_id": case, "frame_count": 9, "sources": sources})
    output = ROOT / ("diagnostic-" + suffix + ".json")
    output.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    return output


if __name__ == "__main__":
    for suffix in SUFFIXES:
        print(build(suffix))
