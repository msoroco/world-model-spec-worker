"""Build explicit synthetic CPU fixtures for exact selected turn cases."""
import hashlib
import json
import math
from pathlib import Path

from prove_observed import rows


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ASSIGNMENT = HERE.parent.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(items):
    return "".join(json.dumps(item, separators=(",", ":"), allow_nan=False) + "\n"
                   for item in items)


def road_source():
    """A bounded crossing-road diagnostic map, never claimed as captured map."""
    def lane(lane_id):
        return (f'<lane id="{lane_id}" type="driving" level="false">'
                '<width sOffset="0" a="3.5" b="0" c="0" d="0" />'
                '</lane>')
    roads = []
    for road_id, x, y, heading, name in (
            (1, -50, 0, 0, "east-west"),
            (2, 0, -50, math.pi / 2, "north-south")):
        roads.append(f'<road id="{road_id}" name="{name}" length="100" junction="-1">'
            '<link/><planView>'
            f'<geometry s="0" x="{x}" y="{y}" hdg="{heading}" length="100"><line/></geometry>'
            '</planView><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
            '<laneSection s="0"><left>' + lane(1) + '</left>'
            '<center><lane id="0" type="none" level="false"/></center>'
            '<right>' + lane(-1) + '</right></laneSection></lanes></road>')
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" '
        'name="C329654-synthetic-two-way-crossing" version="1.00" '
        'date="2026-11-26" north="50" south="-50" east="50" west="-50" '
        'vendor="worker-diagnostic"/>' + "".join(roads) + '</OpenDRIVE>\n')


def build(suffix):
    data = list(rows(suffix))
    case = data[0]["case_id"]
    road = road_source()
    geometry = {"source_kind": "synthetic_cpu",
        "intersection_polygon_xy_m": [[-7, -7], [7, -7], [7, 7], [-7, 7]],
        "synthetic_diagnostic": True}
    survey = {"source_kind": "synthetic_cpu",
        "source_sha256": hashlib.sha256(road.encode()).hexdigest(),
        "intersection_polygon_xy_m": geometry["intersection_polygon_xy_m"],
        "ego_road_lane": [1, -1], "opposing_road_lane": [1, 1],
        "ego_approach_direction_xy": [1, 0],
        "opposing_approach_direction_xy": [-1, 0],
        "synthetic_diagnostic": True}
    mapping, camera, trace, evidence, bodies, graph_rows, graphs = [], [], [], [], [], [], []
    for index, actor in enumerate(data):
        frame = actor["native_frame"]
        time_s = actor["time_s"]
        release = 300 if suffix == "a" else 180
        t = max(0, index - release) / 20
        x, y = (-10 + min(t * 2, 10), max(0, t - 5) * 2)
        body = [[x - 1, y - .8, 0], [x + 1, y - .8, 0],
                [x + 1, y + .8, 0], [x - 1, y + .8, 0]]
        mapping.append({"video_frame": index, "carla_frame": frame,
            "native_frame": frame, "time_s": time_s,
            "camera_native_frames": {name: frame for name in CAMERAS}})
        camera.append({"frame": index, "native_frame": frame,
            "rgb_sha256": {name: "a" * 64 for name in CAMERAS}})
        trace.append({"frame": frame, "time_s": time_s,
            "position": {"x": x, "y": y, "z": 0},
            "position_m": [x, y, 0], "heading_deg": 0 if index < release else 90,
            "speed_mps": actor["ego"]["speed_mps"], "velocity_mps": [0, 0, 0],
            "control": {"throttle": 0, "steer": 0, "brake": 0,
                "hand_brake": False, "reverse": False,
                "manual_gear_shift": False, "gear": 1},
            "nrs253_original_actor_source": actor})
        evidence.append({"original_frame": frame, "replay_frame": frame,
            "recording_time_s": time_s, "synthetic_diagnostic": True,
            "ego": {"position_m": [x, y, 0], "heading_deg": 0,
                "speed_mps": actor["ego"]["speed_mps"],
                "body_vertices_m": body},
            "original_observations": {"frame": frame, "time_s": time_s,
                "participants": []}})
        bodies.append({"frame": frame, "time_s": time_s,
            "subject_body_vertices_m": body, "source_kind": "synthetic_cpu"})
        graph_path = f"graphs/base/{frame:08d}.adapter.json"
        graph_rows.append({"frame": frame, "simulation_time": time_s,
            "time_s": time_s, "base": graph_path,
            "adapter_graph": graph_path, "synthetic_diagnostic": True})
        graphs.append({"path": "capture/native/" + graph_path,
            "attributes": {"frame": frame}, "nodes": [], "edges": []})
    capture_manifest = {"extraction_confirmed": True, "frames": 600,
        "synthetic_diagnostic": True,
        "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
            "trace.jsonl": hashlib.sha256(lines(trace).encode()).hexdigest()}}
    files = {"road.xodr": road, "road_geometry.json": lines([geometry]),
        "map-survey.json": lines([survey]),
        "left-turn-actors.jsonl": lines(data),
        "video_frames.jsonl": lines(mapping),
        "camera-frames.jsonl": lines(camera),
        "trace.jsonl": lines(trace),
        "capture/evidence.jsonl": lines(evidence),
        "interaction_history.jsonl": lines(bodies),
        "capture/native/frames.jsonl": lines(graph_rows),
        "capture/recorder_info.txt": "Create 17: vehicle.lincoln.mkz_2020\n",
        "capture/manifest.json": lines([capture_manifest])}
    spec = {"files": files, "graphs": graphs,
        "videos": [{"path": name + ".mkv", "frames": 600,
            "width": 1920 if name == "overview" else 1280,
            "height": 1080 if name == "overview" else 720,
            "fps": 20, "color": "blue"} for name in CAMERAS]}
    spec_path = HERE / ("selected-" + suffix + "-fixture.json")
    spec_path.write_text(json.dumps(spec, separators=(",", ":"), allow_nan=False) + "\n")
    assignment = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    recipe = {"format": "worker-fixture-recipe", "sources": [{
        "path": "diagnostic-input-assignment.json",
        "source": str(assignment.relative_to(REPO)),
        "sha256": sha(assignment)}],
        "generator": {"source": str(spec_path.relative_to(REPO)),
                      "sha256": sha(spec_path)}}
    recipe_path = HERE / ("selected-" + suffix + "-fixture-recipe.json")
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case_id": case, "spec": str(spec_path),
            "spec_sha256": sha(spec_path), "recipe": str(recipe_path),
            "recipe_sha256": sha(recipe_path)}


if __name__ == "__main__":
    print(json.dumps([build(s) for s in ("a", "b")], indent=2))
