"""Build nine-frame source-shaped software diagnostics for selected cases.

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


def build(suffix):
    case = ROOT.name + "__" + suffix
    spec = copy.deepcopy(json.loads((REPO / "runtime/fixtures/example.json").read_text()))
    files = spec["files"]
    name = "inspected diagnostic map"
    map_bytes = name.encode()
    scene = {
        "case_id": case,
        "crossing": {"id": "median-crossing-diagnostic", "kind": "median_opening_roadway_crossing",
                     "bounds_xy_m": [-2, -2, 2, 2],
                     "opendrive_sha256": hashlib.sha256(map_bytes).hexdigest()},
        "ego_highway": "north-south", "other_highway": "east-west",
        "highway_identity_source": "diagnostic highway source",
        "public_access_source": "diagnostic highway source",
        "device_inventory_source": "diagnostic device source",
        "governing_signal": {"kind": "official_traffic_signal", "readback_state": "inoperative",
                             "controlled_approach_road_ids": [1, 2]},
        "ego_approach_road_id": 1, "other_approach_road_id": 2,
        "ego_blueprint": "vehicle.car.ego", "other_blueprint": "vehicle.car.other",
        "ego_route_xy_m": [[0, -10], [0, 0], [0, 10]],
        "other_route_xy_m": [[-10, 0], [0, 0], [10, 0]],
        "subsection_4_applicability_review": "unresolved diagnostic context",
        "opposing_left_turn_excluded_source": "unresolved diagnostic context",
    }
    rows = [json.loads(s) for s in files["video_frames.jsonl"].splitlines()]
    if len(rows) != 9:
        raise ValueError("runtime diagnostic scaffold frame count changed")
    ego_entry, ego_exit = (5, 7) if suffix == "precedence" else (2, 4)
    frames = []
    for index, mapped in enumerate(rows):
        ego_y = -10 if index < ego_entry else (0 if index < ego_exit else 10)
        other_x = -10 if index < 1 else (0 if index < 3 else 10)
        frames.append({"frame": index, "time_s": index / 20,
                       "native_frame_id": mapped["carla_frame"],
                       "native_elapsed_seconds": mapped["time_s"],
                       "signal_readback": "inoperative",
                       "ego": {"id": 10, "road_id": 1,
                               "body_vertices_xy_m": body(0, ego_y)},
                       "other": {"id": 11, "road_id": 2,
                                 "body_vertices_xy_m": body(other_x, 0)}})
    trace = {"case_id": case, "map_sha256": scene["crossing"]["opendrive_sha256"],
             "actor_ids": {"ego": 10, "other": 11}, "frames": frames}
    files["scene.json"] = packed(scene)
    files["native_trace.json"] = packed(trace)
    files["crossing_history.jsonl"] = "".join(json.dumps({
        "frame": row["native_frame_id"],
        "time_s": row["native_elapsed_seconds"],
        "ego_vertices_m": row["ego"]["body_vertices_xy_m"]}) + "\n"
        for row in frames)
    files["opendrive.xodr"] = name
    files["device_inventory.json"] = packed({"source": "diagnostic only", "signal": "inoperative"})
    files["highway_identity.json"] = packed({"ego_highway": "north-south",
                                              "other_highway": "east-west",
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
                 "device_inventory": "device_inventory.json"}
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
    for suffix in ("precedence", "advance"):
        print(build(suffix))
