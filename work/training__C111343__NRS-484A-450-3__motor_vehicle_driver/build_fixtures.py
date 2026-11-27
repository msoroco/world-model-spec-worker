"""Text-only, explicitly synthetic source bundles for both exact case checks."""

import hashlib
import json
from pathlib import Path

from measure_yield_crosswalk import CAMERAS, HASHES
from prove_yield_crosswalk import trace
from yield_crosswalk_scene import CASES, request

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


def body(x, y, length=4.5):
    return [[x + sx * length / 2, y + sy * .9, z]
            for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1.5)]


def build(slug):
    root = HERE / "selected-source" / slug
    root.mkdir(parents=True, exist_ok=True)
    scene = request(slug)
    (root / "road.xodr").write_text(scene["road_opendrive"] + "\n")
    map_hash = sha(root / "road.xodr")
    put(root / "yield_sign.json", {"id": "yield-111343", "map_readback_sha256": map_hash,
                                   "synthetic_diagnostic": True})
    kind = scene["reference_kind"]
    reference_file = {"crosswalk": "near_crosswalk.json", "stop_line": "marked_stop_line.json",
                      "viewpoint": "nearest_viewpoint.json"}[kind]
    put(root / reference_file, {"reference_kind": kind, "near_x_m": -6,
        "far_x_m": scene["reference_far_x_m"],
        "crosswalk_present": kind == "crosswalk", "marked_stop_line_present": kind == "stop_line",
        "candidate_viewpoint_only": kind == "viewpoint", "map_readback_sha256": map_hash,
        "synthetic_diagnostic": True})
    put(root / "intersecting_traffic.json", {"actor_id": 2,
        "body_source": "intersecting_body.jsonl", "motion_source": "yield_motion.jsonl",
        "map_readback_sha256": map_hash, "synthetic_diagnostic": True})
    put(root / "safety_context.json", {"traffic_source": "intersecting_traffic.json",
        "motion_source": "yield_motion.jsonl", "safety_stop_required": "unassessed",
        "independent_judgment_required": True, "time_to_conflict_legal_cutoff": None,
        "synthetic_diagnostic": True})
    motion = []
    frames = []
    core = []
    ego_bodies = []
    other_bodies = []
    evidence = []
    native_frames = []
    for row in trace(slug):
        i = row["video_frame"]
        native = row["native_frame"]
        x = row["ego_x_m"]
        y = row["intersecting_vehicle_y_m"]
        eb = body(x, -1.75)
        ob = body(1.75, y)
        motion.append({**row, "ego_actor_id": 1, "intersecting_actor_id": 2,
                       "intersecting_speed_mps": 5})
        frames.append({"video_frame": i, "native_frame": native, "carla_frame": native,
            "time_s": row["time_s"], "source_cameras": row["source_cameras"],
            "camera_native_frames": row["source_cameras"]})
        core.append({"frame": native, "time_s": row["time_s"],
            "position": {"x": x, "y": -1.75, "z": .5},
            "position_m": [x, -1.75, .5], "heading_deg": 0,
            "speed_mps": row["ego_speed_mps"], "speed_mph": row["ego_speed_mps"] * 2.2369362921,
            "control": {"throttle": 0, "brake": 0, "hand_brake": False},
            "velocity_mps": [row["ego_speed_mps"], 0, 0],
            "synthetic_diagnostic": True, "speed_provenance": "synthetic_native_sample"})
        ego_bodies.append({"native_frame": native, "actor_id": 1, "body_vertices_m": eb})
        other_bodies.append({"native_frame": native, "actor_id": 2, "body_vertices_m": ob})
        evidence.append({"original_frame": native, "replay_frame": native,
            "actor_id": 1, "recording_time_s": row["time_s"],
            "replay_simulation_time_s": row["time_s"],
            "ego": {"position_m": [x, -1.75, .5], "heading_deg": 0,
                    "speed_mps": row["ego_speed_mps"], "body_vertices_m": eb,
                    "speed_provenance": "synthetic_native_sample"},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                   "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 111343, "section_id": 0,
                                          "lane_id": -1, "s_m": x + 80}},
            "synthetic_diagnostic": True})
        native_frames.append({"frame": native, "time_s": row["time_s"],
            "simulation_time": row["time_s"], "synthetic_diagnostic": True,
            "adapter_graph": f"graphs/base/{native:09d}.adapter.json"})
    for filename, values in (("yield_motion.jsonl", motion), ("video_frames.jsonl", frames),
                             ("trace.jsonl", core), ("ego_body.jsonl", ego_bodies),
                             ("intersecting_body.jsonl", other_bodies),
                             ("capture/evidence.jsonl", evidence),
                             ("capture/native/frames.jsonl", native_frames)):
        lines(root / filename, values)
    if kind == "viewpoint":
        lines(root / "viewpoint_sight_rays.jsonl", [
            {"native_frame": row["native_frame"], "time_s": row["time_s"],
             "ego_eye_m": [row["ego_x_m"], -1.75, 1.25],
             "traffic_target_m": [1.75, row["intersecting_vehicle_y_m"], 1],
             "hit_labels": ["synthetic_fixture"], "nearest_legal_viewpoint_unassessed": True}
            for row in motion])
    put(root / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "native_executed": False})
    (root / "capture/recorder_info.txt").write_text(
        "Synthetic diagnostic recorder summary; no CARLA server used.\n"
        "Create 1: vehicle.tesla.model3 (0) at (-45, -1.75, 0.5)\n")
    put(root / "capture/manifest.json", {"extraction_confirmed": True, "frames": 600,
        "required_observations": [], "synthetic_diagnostic": True,
        "sources": {"road.xodr": map_hash, "trace.jsonl": sha(root / "trace.jsonl")}})
    sources = {"native_map": "road.xodr", "yield_sign": "yield_sign.json",
        "stop_reference": reference_file, "ego_body": "ego_body.jsonl",
        "ego_motion": "yield_motion.jsonl", "intersecting_traffic": "intersecting_traffic.json",
        "safety_context": "safety_context.json", "camera_manifest": "video_frames.jsonl"}
    if kind == "viewpoint":
        sources["sight_rays"] = "viewpoint_sight_rays.jsonl"
    assert set(HASHES) <= set(sources)
    put(root / "yield_context.json", {"case_id": AID + "__" + slug,
        "source_kind": "synthetic_yield_fixture", "source_files": sources,
        **{name + "_sha256": sha(root / path) for name, path in sources.items()},
        "governing_yield_sign": True, "near_side_crosswalk": kind == "crosswalk",
        "reference_kind": kind, "reference_source": reference_file,
        "reference_near_x_m": -6, "reference_far_x_m": scene["reference_far_x_m"],
        "intersection_near_x_m": -3.5, "safety_context_present": True,
        "safety_stop_required": "unassessed", "legal_compliance": "unassessed",
        "physical_acceptance_claimed": False})
    items = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(root))
            items.append({"path": relative, "source": str(path.relative_to(REPO)),
                          "sha256": sha(path)})
    generator = json.loads(GENERIC.read_text())
    generator["videos"] = [{"path": name + ".mkv", "frames": 600,
        "width": 1920 if name == "overview" else 1280,
        "height": 1080 if name == "overview" else 720,
        "fps": 20, "color": color}
        for name, color in (("overview", "blue"), ("driver_reference", "green"),
                            ("reference_corner", "white"), ("approach", "red"))]
    generator_path = HERE / ("selected-generator-" + slug + ".json")
    put(generator_path, generator)
    recipe = {"format": "worker-fixture-recipe", "sources": items,
              "generator": {"source": str(generator_path.relative_to(REPO)),
                            "sha256": sha(generator_path)}}
    recipe_path = HERE / ("selected-recipe-" + slug + ".json")
    put(recipe_path, recipe)
    return {"case_id": AID + "__" + slug, "recipe": str(recipe_path.relative_to(REPO)),
            "sources": len(items), "generator_sha256": sha(generator_path)}


if __name__ == "__main__":
    print(json.dumps([build(slug) for slug in CASES], sort_keys=True))
