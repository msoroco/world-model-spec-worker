"""Build explicit 600-frame diagnostic sources for both beam requests.

All returned files are textual. Generated videos and adapter graphs are made
only by the pinned fixture generator in ignored .runtime-work on demand.
"""
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "native"))
from beam_scene import CAMERAS, MODES, beam_request, road_opendrive  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def bbox(x, y):
    return [[x + dx, y + dy, z] for dx in (-2, 2)
            for dy in (-.9, .9) for z in (0, 1.5)]


def build(case):
    aid = "training__C183394__NRS-484D-215-1__motor_vehicle_driver"
    case_id = aid + "__selected_6fb122bc__" + case
    dest = ROOT / "fixture-source" / case
    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    write(dest / "road.xodr", road_opendrive() + "\n")
    for name, value in {
        "road-position-source.json": {"road_position": "adjacent_shoulder",
            "map_and_adjacency_source": "synthetic authored OpenDRIVE lane -2 adjacent lane -1",
            "highway_status_review_required": True},
        "lighting-trigger-source.json": {"lighting_trigger": "night_interval",
            "original_trigger_source": "synthetic night request only",
            "NRS_484D_100_review_required": True, "civil_time_condition_verified": False},
        "oncoming-driver-source.json": {"oncoming_actor_source": "synthetic opposed actor",
            "driver_eye_identity_review_required": True},
        "eye-region-source.json": {"driver_reference_camera": "driver_reference",
            "pixel_review_required": True, "original_driver_eye_region_verified": False},
        "acquisition-provenance.json": {"provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "original_native_observed": False},
    }.items():
        dump(dest / name, value)
    beam, frames, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    for i in range(600):
        t = i / 20
        ex, ox = -100 + 2.5*t, 100 - 2.5*t
        ey, oy = -5.0, 1.75
        separation = ((ex-ox)**2 + (ey-oy)**2)**.5
        state = beam_request(MODES[case], separation)
        beam.append({"frame": i, "native_frame": i, "time_s": t,
            "ego_x_m": ex, "ego_y_m": ey, "ego_heading_x": 1, "ego_heading_y": 0,
            "oncoming_x_m": ox, "oncoming_y_m": oy,
            "oncoming_heading_x": -1, "oncoming_heading_y": 0,
            "ego_speed_mps": 2.5, "oncoming_speed_mps": 2.5,
            "requested_beam_state": state,
            "observed_light_state_bits": 1 + (2 if state == "low_beam" else 4),
            "lamp_state_source": "synthetic diagnostic state",
            "eye_region_pixels_retained": True})
        frames.append({"video_frame": i, "native_frame": i,
                       "carla_frame": i, "time_s": t})
        trace.append({"frame": i, "time_s": t,
            "position": {"x": ex, "y": ey, "z": .5},
            "position_m": [ex, ey, .5], "heading_deg": 0,
            "velocity_mps": [2.5, 0, 0], "speed_mps": 2.5,
            "speed_mph": 2.5/.44704,
            "control": {"throttle": 0, "brake": 0, "hand_brake": False}})
        vertices = bbox(ex, ey)
        evidence.append({"actor_id": 107, "ego": {"body_vertices_m": vertices,
            "heading_deg": 0, "position_m": [ex, ey, .5], "speed_mps": 2.5,
            "speed_provenance": "synthetic_native_sample",
            "synthetic_diagnostic": True},
            "original_frame": i, "recording_time_s": t, "replay_frame": i,
            "replay_simulation_time_s": t,
            "world": {"road_projection": {"lane_id": -2, "road_id": 183394,
                "s_m": ex+250, "section_id": 0},
                "weather": {"cloudiness": 0, "fog_density": 0,
                            "precipitation": 0, "wetness": 0}}})
        graph_path = f"capture/native/graphs/base/{i:08d}.adapter.json"
        native_frames.append({"frame": i, "simulation_time": t,
            "adapter_graph": f"graphs/base/{i:08d}.adapter.json",
            "base": f"graphs/base/{i:08d}.adapter.json", "nodes": 2, "edges": 0})
        graphs.append({"path": graph_path,
            "attributes": {"frame": i, "simulation_time_s": t,
                           "source": "C183394 beam CPU diagnostic",
                           "synthetic_diagnostic": True}, "edges": [],
            "nodes": [
                {"id": "ego", "attributes": {"entity_id": 107,
                    "forward": [1, 0, 0], "sem_class": "ego",
                    "threedbbox": vertices, "vertex": [ex, ey, .5]}},
                {"id": "oncoming", "attributes": {"entity_id": 108,
                    "forward": [-1, 0, 0], "sem_class": "vehicle",
                    "threedbbox": bbox(ox, oy), "vertex": [ox, oy, .5]}},
            ]})
    for name, rows in (("beam-rows.jsonl", beam),
                       ("video_frames.jsonl", frames), ("trace.jsonl", trace),
                       ("capture/evidence.jsonl", evidence)):
        write(dest / name, "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
    write(dest / "capture/recorder_info.txt",
          "synthetic CPU diagnostic; no CARLA recorder\n"
          "Create 107: vehicle.carlamotors.carlacola (0)\n")
    dump(dest / "capture/manifest.json", {
        "status": "draft", "acquisition": "original_live_run",
        "case_id": case_id, "frames": 600, "required_observations": [],
        "extraction_confirmed": True,
        "sources": {"road.xodr": sha(dest / "road.xodr"),
                    "trace.jsonl": sha(dest / "trace.jsonl")},
        "observation_contract_version": 1,
        "synthetic_diagnostic": True})
    sources = ("road.xodr", "beam-rows.jsonl", "video_frames.jsonl",
               "road-position-source.json", "lighting-trigger-source.json",
               "oncoming-driver-source.json", "eye-region-source.json")
    dump(dest / "beam-context.json", {"case_id": case_id,
        "deeming_invoked": False, "legal_verdict_claimed": False,
        "source_sha256": {name: sha(dest / name) for name in sources}})
    spec = {"files": {"capture/native/frames.jsonl": "".join(
                json.dumps(row) + "\n" for row in native_frames)},
            "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 600,
                        "width": 1920 if name == "overview" else 1280,
                        "height": 1080 if name == "overview" else 720,
                        "fps": 20, "color": "black"} for name in CAMERAS]}
    spec_path = ROOT / ("fixture-spec-" + case + ".json")
    dump(spec_path, spec)
    inventory = sorted([p for p in dest.rglob("*") if p.is_file()])
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                            "sha256": sha(spec_path)},
              "sources": [{"path": p.relative_to(dest).as_posix(),
                           "source": p.relative_to(REPO).as_posix(),
                           "sha256": sha(p)} for p in inventory]}
    dump(ROOT / ("fixture-recipe-" + case + ".json"), recipe)
    return {"case": case, "source_files": len(inventory),
            "spec_bytes": spec_path.stat().st_size}


if __name__ == "__main__":
    print(json.dumps([build(case) for case in MODES], indent=2))
