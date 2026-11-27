"""Text-only original-shaped bus diagnostics; never physical evidence."""

import hashlib
import json
from pathlib import Path

from native.bus_scene import CAMERAS, FRAMES, RATE_HZ, request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
GENERIC = REPO / "work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/selected-generator-complete_stop_then_yield.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"
                            for value in values))


def body(x, y, length=4.5, width=1.8):
    return [[x + sx * length / 2, y + sy * width / 2, z]
            for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1.5)]


def build(case):
    slug = case["case_id"].removeprefix(AID + "__")
    scene = request(case["requested_setting"],
                    vehicle_class=case["vehicle_class_requested"],
                    emergency=case["emergency_requested"])
    root = HERE / "selected-source" / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / "road.xodr").write_text(scene["road_opendrive"] + "\n")
    map_hash = sha(root / "road.xodr")
    motion, frames, trace, buses, passengers, evidence, native_frames = [], [], [], [], [], [], []
    for i in range(FRAMES):
        native = 800000 + i
        time_s = i / RATE_HZ
        x = -35 + .24 * min(i, 90) + .12 * max(0, i - 480)
        bus_speed = 4.8 if i < 90 else (0 if i < 480 else 2.4)
        pedestrian_y = -5.5 + 2.3 * min(1, max(0, (i - 170) / 90))
        bus_body = body(x, -1.75, 8.0, 2.5)
        passenger_body = body(-10, pedestrian_y, .5, .4)
        frame = {"video_frame": i, "native_frame": native, "carla_frame": native,
                 "time_s": time_s,
                 "source_cameras": {name: native for name in CAMERAS},
                 "camera_rgb_sha256": {name: hashlib.sha256((slug + name + str(i)).encode()).hexdigest()
                                       for name in CAMERAS}}
        frames.append(frame)
        motion.append({**frame, "bus_actor_id": 1, "passenger_actor_id": 2,
                       "bus_speed_mps": bus_speed, "bus_center_m": [x, -1.75, .5],
                       "passenger_center_m": [-10, pedestrian_y, .5],
                       "door_open_request_active": 140 <= i < 420,
                       "mechanical_fault_request_active": case["emergency_requested"] and 90 <= i < 480,
                       "actual_door_state_observed": False,
                       "actual_passenger_transfer_observed": False,
                       "emergency_requested": case["emergency_requested"]})
        buses.append({"native_frame": native, "actor_id": 1, "body_vertices_m": bus_body})
        passengers.append({"native_frame": native, "actor_id": 2,
                           "body_vertices_m": passenger_body})
        trace.append({"frame": native, "time_s": time_s,
                      "position": {"x": x, "y": -1.75, "z": .5},
                      "position_m": [x, -1.75, .5], "heading_deg": 0,
                      "speed_mps": bus_speed, "speed_mph": bus_speed * 2.2369362921,
                      "control": {"throttle": 0, "brake": 0, "hand_brake": False},
                      "velocity_mps": [bus_speed, 0, 0],
                      "synthetic_diagnostic": True,
                      "speed_provenance": "synthetic_native_sample"})
        evidence.append({"original_frame": native, "replay_frame": native,
            "actor_id": 1, "recording_time_s": time_s, "replay_simulation_time_s": time_s,
            "ego": {"position_m": [x, -1.75, .5], "heading_deg": 0,
                    "speed_mps": bus_speed, "body_vertices_m": bus_body,
                    "speed_provenance": "synthetic_native_sample"},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                   "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 378131, "section_id": 0,
                                          "lane_id": -1, "s_m": x + 80}},
            "synthetic_diagnostic": True})
        native_frames.append({"frame": native, "time_s": time_s,
            "simulation_time": time_s, "synthetic_diagnostic": True,
            "adapter_graph": f"graphs/base/{native:09d}.adapter.json"})
    for name, rows in (("bus_motion.jsonl", motion), ("video_frames.jsonl", frames),
                       ("trace.jsonl", trace), ("bus_body.jsonl", buses),
                       ("passenger_body.jsonl", passengers),
                       ("capture/evidence.jsonl", evidence),
                       ("capture/native/frames.jsonl", native_frames)):
        lines(root / name, rows)
    put(root / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "native_executed": False})
    (root / "capture/recorder_info.txt").write_text(
        "Synthetic bus loading diagnostic; no CARLA server used.\n"
        "Create 1: vehicle.mitsubishi.fusorosa (0) at (-35, -1.75, 0.5)\n")
    put(root / "capture/manifest.json", {"extraction_confirmed": True,
        "frames": FRAMES, "required_observations": [], "synthetic_diagnostic": True,
        "sources": {"road.xodr": map_hash, "trace.jsonl": sha(root / "trace.jsonl")}})
    sources = {"native_map": "road.xodr", "motion": "bus_motion.jsonl",
               "bus_body": "bus_body.jsonl", "passenger_body": "passenger_body.jsonl",
               "camera_manifest": "video_frames.jsonl"}
    put(root / "bus_context.json", {
        "source_kind": "synthetic_native_sample", "source_files": sources,
        **{name + "_sha256": sha(root / filename) for name, filename in sources.items()},
        "zone_kind_requested": scene["zone_kind"], "zone_id": scene["zone_id"],
        "route_id_requested": scene["route_id"],
        "vehicle_class_requested": scene["vehicle_class_requested"],
        "emergency_requested": scene["emergency_requested"],
        "designation_authority_confirmed": False,
        "actual_loading_confirmed": False, "physical_acceptance_claimed": False})
    inventory = [{"path": str(path.relative_to(root)),
                  "source": str(path.relative_to(REPO)), "sha256": sha(path)}
                 for path in sorted(root.rglob("*")) if path.is_file()]
    generator = json.loads(GENERIC.read_text())
    generator["videos"] = [{"path": name + ".mkv", "frames": FRAMES,
        "width": 1920 if name == "overview" else 1280,
        "height": 1080 if name == "overview" else 720,
        "fps": RATE_HZ, "color": color} for name, color in
        (("overview", "blue"), ("approach", "red"),
         ("reference_corner", "white"), ("driver_reference", "green"))]
    generator_path = HERE / ("selected-generator-" + slug + ".json")
    put(generator_path, generator)
    recipe = {"format": "worker-fixture-recipe", "sources": inventory,
              "generator": {"source": str(generator_path.relative_to(REPO)),
                            "sha256": sha(generator_path)}}
    recipe_path = HERE / ("selected-recipe-" + slug + ".json")
    put(recipe_path, recipe)
    return {"case_id": case["case_id"], "sources": len(inventory),
            "recipe": str(recipe_path.relative_to(REPO))}


if __name__ == "__main__":
    plan = json.loads((HERE / "case-plan.json").read_text())
    print(json.dumps([build(case) for case in plan["cases"]], sort_keys=True))
