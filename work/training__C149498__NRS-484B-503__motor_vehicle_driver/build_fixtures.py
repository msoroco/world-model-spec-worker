"""Text-only synthetic passenger curb sources for current-runtime CPU checks."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from native.loading_scene import CAMERAS, CASES, FRAMES, RATE_HZ, request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
PREFIX = AID + "__selected_bae4893e__"
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


def build(slug):
    scene = request(slug)
    root = HERE / "selected-source" / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / "road.xodr").write_text(scene["road_opendrive"] + "\n")
    map_hash = sha(root / "road.xodr")
    put(root / "loading_zone.json", {
        "object_id": scene["zone"]["object_id"], "sign_id": scene["zone"]["sign_id"],
        "sign_text_hours": [scene["zone"]["hours_start"], scene["zone"]["hours_end"]],
        "time_zone": scene["zone"]["time_zone"], "map_readback_sha256": map_hash,
        "regulatory_authority_confirmed": False, "synthetic_diagnostic": True})
    start = datetime.fromisoformat(scene["zone"]["civil_timestamp_start"])
    resume = scene["controller"]["resume_request_frame"]
    moving = scene["controller"]["halt_request_frame"]
    motion, frames, core, bodies, passengers, evidence, native_frames = [], [], [], [], [], [], []
    for i in range(FRAMES):
        native = 800000 + i
        time_s = i / RATE_HZ
        x = -35 + .24 * min(i, moving) + (.12 * max(0, i - resume))
        speed = 4.8 if i < moving else (0 if i < resume else 2.4)
        y = -5.5 if not CASES[slug] else (-5.5 + 2.3 * min(1, max(0, (i - 170) / 90)))
        ego = body(x, -1.75)
        pedestrian = body(-10, y, .5, .4)
        camera_frames = {name: native for name in CAMERAS}
        camera_hashes = {name: hashlib.sha256((slug + name + str(i)).encode()).hexdigest()
                         for name in CAMERAS}
        frame = {"video_frame": i, "native_frame": native, "carla_frame": native,
                 "time_s": time_s, "source_cameras": camera_frames,
                 "camera_rgb_sha256": camera_hashes}
        frames.append(frame)
        motion.append({**frame, "ego_actor_id": 1, "passenger_actor_id": 2,
            "vehicle_speed_mps": speed, "vehicle_center_m": [x, -1.75, .5],
            "passenger_center_m": [-10, y, .5],
            "door_open_request_active": scene["controller"]["door_open_request_frame"] is not None and
                scene["controller"]["door_open_request_frame"] <= i < scene["controller"]["door_close_request_frame"],
            "civil_timestamp": (start + timedelta(seconds=time_s)).isoformat(),
            "occupant_count_observed": False, "actual_door_state_observed": False})
        bodies.append({"native_frame": native, "actor_id": 1, "body_vertices_m": ego})
        passengers.append({"native_frame": native, "actor_id": 2, "body_vertices_m": pedestrian})
        core.append({"frame": native, "time_s": time_s,
            "position": {"x": x, "y": -1.75, "z": .5},
            "position_m": [x, -1.75, .5], "heading_deg": 0,
            "speed_mps": speed, "speed_mph": speed * 2.2369362921,
            "control": {"throttle": 0, "brake": 0, "hand_brake": False},
            "velocity_mps": [speed, 0, 0], "synthetic_diagnostic": True,
            "speed_provenance": "synthetic_native_sample"})
        evidence.append({"original_frame": native, "replay_frame": native,
            "actor_id": 1, "recording_time_s": time_s, "replay_simulation_time_s": time_s,
            "ego": {"position_m": [x, -1.75, .5], "heading_deg": 0,
                    "speed_mps": speed, "body_vertices_m": ego,
                    "speed_provenance": "synthetic_native_sample"},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                   "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 149498, "section_id": 0,
                                          "lane_id": -1, "s_m": x + 80}},
            "synthetic_diagnostic": True})
        native_frames.append({"frame": native, "time_s": time_s,
            "simulation_time": time_s, "synthetic_diagnostic": True,
            "adapter_graph": f"graphs/base/{native:09d}.adapter.json"})
    for filename, values in (("loading_motion.jsonl", motion), ("video_frames.jsonl", frames),
                             ("trace.jsonl", core), ("ego_body.jsonl", bodies),
                             ("passenger_body.jsonl", passengers),
                             ("capture/evidence.jsonl", evidence),
                             ("capture/native/frames.jsonl", native_frames)):
        lines(root / filename, values)
    put(root / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "native_executed": False})
    (root / "capture/recorder_info.txt").write_text(
        "Synthetic passenger curb diagnostic; no CARLA server used.\n"
        "Create 1: vehicle.tesla.model3 (0) at (-35, -1.75, 0.5)\n")
    put(root / "capture/manifest.json", {"extraction_confirmed": True,
        "frames": FRAMES, "required_observations": [], "synthetic_diagnostic": True,
        "sources": {"road.xodr": map_hash, "trace.jsonl": sha(root / "trace.jsonl")}})
    sources = {"native_map": "road.xodr", "zone": "loading_zone.json",
        "motion": "loading_motion.jsonl", "ego_body": "ego_body.jsonl",
        "passenger_body": "passenger_body.jsonl", "camera_manifest": "video_frames.jsonl"}
    put(root / "loading_context.json", {"case_id": PREFIX + slug,
        "source_kind": "synthetic_passenger_curb_fixture", "source_files": sources,
        **{name + "_sha256": sha(root / filename) for name, filename in sources.items()},
        "requested_passenger_transfer": CASES[slug],
        "actual_passenger_transfer_confirmed": False,
        "occupant_count_observed": False, "regulatory_authority_confirmed": False,
        "expeditiousness_conclusion": None, "physical_acceptance_claimed": False})
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items.append({"path": str(path.relative_to(root)),
                          "source": str(path.relative_to(REPO)), "sha256": sha(path)})
    generator = json.loads(GENERIC.read_text())
    generator["videos"] = [{"path": name + ".mkv", "frames": FRAMES,
        "width": 1920 if name == "overview" else 1280,
        "height": 1080 if name == "overview" else 720,
        "fps": RATE_HZ, "color": color} for name, color in
        (("overview", "blue"), ("approach", "red"),
         ("reference_corner", "white"), ("driver_reference", "green"))]
    generator_path = HERE / ("selected-generator-" + slug + ".json")
    put(generator_path, generator)
    recipe = {"format": "worker-fixture-recipe", "sources": items,
        "generator": {"source": str(generator_path.relative_to(REPO)),
                      "sha256": sha(generator_path)}}
    recipe_path = HERE / ("selected-recipe-" + slug + ".json")
    put(recipe_path, recipe)
    return {"case_id": PREFIX + slug, "sources": len(items),
            "recipe": str(recipe_path.relative_to(REPO))}


if __name__ == "__main__":
    print(json.dumps([build(slug) for slug in CASES], sort_keys=True))
