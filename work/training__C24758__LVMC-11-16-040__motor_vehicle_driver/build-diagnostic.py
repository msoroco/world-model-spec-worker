"""Construct explicit synthetic source fixtures for exact saved-source CPU tests."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DONOR = REPO / "work/training__C229410__NRS-484B-450-1j__motor_vehicle_driver/selected-source/controlled_1"
GENERATOR = REPO / "work/training__C229397__NRS-484B-450-1e__motor_vehicle_driver/selected-generator-witness_1.json"
GEOMETRY = REPO / "work/training__C229397__NRS-484B-450-1e__motor_vehicle_driver/native/geometry.py"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def build(suffix, speed):
    case = ROOT.name + "__" + suffix
    folder = ROOT / "diagnostic-source" / suffix
    folder.mkdir(parents=True, exist_ok=True)
    source_names = ("acquisition-provenance.json", "capture/evidence.jsonl",
                    "capture/manifest.json", "capture/native/frames.jsonl",
                    "capture/recorder_info.txt", "trace.jsonl", "video_frames.jsonl")
    for name in source_names:
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR / name, target)
    module_spec = importlib.util.spec_from_file_location("c24758_diagnostic_geometry", GEOMETRY)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    (folder / "road.xodr").write_text(module.open_drive() + "\n")
    (folder / "native-map-readback.xodr").write_bytes((folder / "road.xodr").read_bytes())
    generation = json.loads(GENERATOR.read_text())
    trace = load_rows(folder / "trace.jsonl")
    mapping = load_rows(folder / "video_frames.jsonl")
    evidence = load_rows(folder / "capture/evidence.jsonl")
    native_frames = load_rows(folder / "capture/native/frames.jsonl")
    require_count = 600
    if not (len(trace) == len(mapping) == len(evidence) == len(native_frames) == len(generation["graphs"]) == require_count):
        raise ValueError("Donor diagnostic Core frame count changed")
    rgb = {name: hashlib.sha256((bytes((0, 0, 0)) if name == "overview" else
                                 bytes((255, 255, 255))) * (1920 * 1080 if name == "overview" else 1280 * 720)).hexdigest()
           for name in CAMERAS}
    generation["videos"] = [{"path": name + ".mkv", "frames": 600,
        "width": 1920 if name == "overview" else 1280,
        "height": 1080 if name == "overview" else 720,
        "fps": 20, "color": "black" if name == "overview" else "white"}
        for name in CAMERAS]
    raw, frame_map, review_frames = [], [], []
    approach_ids = ("1:-1", "3:-1")
    for i in range(600):
        native_frame = mapping[i]["native_frame"]
        time_s = i / 20
        x = -45 + speed * time_s
        position = [x, -2, 1]
        body = [[x + dx, -2 + dy, z] for dx, dy in
                ((-2, -1), (-2, 1), (2, -1), (2, 1)) for z in (0, 2)]
        trace[i].update(frame=native_frame, time_s=time_s,
            position={"x": x, "y": -2, "z": 1}, position_m=position,
            heading_deg=0, speed_mps=speed,
            speed_mph=speed * 2.2369362921, velocity_mps=[speed, 0, 0])
        mapping[i].update(carla_frame=native_frame, time_s=time_s)
        evidence[i].update(original_frame=native_frame, replay_frame=native_frame,
                           recording_time_s=time_s, replay_simulation_time_s=time_s)
        evidence[i]["ego"].update(position_m=position, heading_deg=0,
                                   speed_mps=speed, body_vertices_m=body)
        observed = evidence[i].get("original_observations")
        if observed:
            observed.update(frame=native_frame, time_s=time_s)
            for participant in observed.get("participants", []):
                if participant.get("actor_id") == evidence[i]["actor_id"]:
                    participant.update(position_m=position, velocity_mps=[speed, 0, 0],
                                       speed_mps=speed, heading_deg=0, body_vertices_m=body)
            generation["graphs"][i]["attributes"]["observed_evidence"] = observed
        if generation["graphs"][i]["nodes"]:
            generation["graphs"][i]["nodes"][0]["attributes"].update(vertex=position, threedbbox=body)
        native_frames[i]["simulation_time"] = time_s
        frame_map.append({"video_frame": i, "native_frame": native_frame,
                          "time_s": time_s, "original_rgb_sha256": rgb})
        rays = [{"target_xyz_m": [0, 0, 0], "ray_length_m": abs(x),
                 "hits": [{"xyz_m": [0, 0, 0], "label": "Buildings"}]}] * 7
        raw.append({"video_frame": i, "native_frame": native_frame,
                    "ego_speed_mps": speed, "ego_xyz_m": position,
                    "ego_yaw_deg": 0,
                    "distance_to_boundary_euclidean_m": max(0, -x),
                    "ego_native_junction_id": 100 if 0 <= x <= 14 else None,
                    "original_native_sight_rays": rays})
        ray_hash = hashlib.sha256(json.dumps(rays, sort_keys=True).encode()).hexdigest()
        review_frames.append({"frame": i, "native_frame": native_frame,
            "sight_ray_sha256": ray_hash, "camera_rgb_sha256": rgb,
            "distance_to_boundary_m": -x,
            "intersection_clear_100ft": False,
            "entering_approach_views": {key: {"clear_100ft": False,
                                             "traffic_visible_100ft": False}
                                        for key in approach_ids}})
    for name, data in (("trace.jsonl", trace), ("video_frames.jsonl", mapping),
                       ("capture/evidence.jsonl", evidence),
                       ("capture/native/frames.jsonl", native_frames)):
        (folder / name).write_text(lines(data))
    (folder / "frame-map.json").write_text(json.dumps(frame_map, separators=(",", ":")) + "\n")
    (folder / "native-ego-readback.jsonl").write_text(lines(raw))
    context = {"assignment_id": ROOT.name, "case_id": case,
               "native_map_sha256": sha(folder / "native-map-readback.xodr"),
               "junction_id": 100,
               "entering_approach_ray_targets": {key: [] for key in approach_ids}}
    write(folder / "native-context-readback.json", context)
    names = ("frame-map.json", "native-ego-readback.jsonl",
             "native-context-readback.json", "native-map-readback.xodr")
    review = {"assignment_id": ROOT.name, "case_id": case,
              "source_sha256": {name: sha(folder / name) for name in names},
              "reviewer": {"id": "synthetic_cpu_fixture",
                           "method": "diagnostic ray and pixel shape; no Native claim"},
              "exceptions": {key: {"value": False,
                                   "source": "native-map-readback.xodr",
                                   "reviewed_by": "synthetic_cpu_fixture"}
                             for key in ("through_street", "traffic_controlled_intersection")},
              "frames": review_frames}
    write(folder / "review.json", review)
    manifest = json.loads((folder / "capture/manifest.json").read_text())
    manifest["case_id"] = case
    manifest["frames"] = 600
    manifest["sources"] = {"road.xodr": sha(folder / "road.xodr"),
                           "trace.jsonl": sha(folder / "trace.jsonl")}
    write(folder / "capture/manifest.json", manifest)
    gen_path = ROOT / ("diagnostic-generator-" + suffix + ".json")
    write(gen_path, generation)
    all_sources = (*source_names, "road.xodr", "native-map-readback.xodr",
                   "frame-map.json", "native-ego-readback.jsonl",
                   "native-context-readback.json", "review.json")
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": name, "source": str((folder / name).relative_to(REPO)),
                           "sha256": sha(folder / name)} for name in all_sources],
              "generator": {"source": str(gen_path.relative_to(REPO)),
                            "sha256": sha(gen_path)}}
    write(ROOT / ("diagnostic-recipe-" + suffix + ".json"), recipe)
    print(suffix, "generator_bytes", gen_path.stat().st_size,
          "largest_source_bytes", max((folder / name).stat().st_size for name in all_sources))


if __name__ == "__main__":
    for suffix, speed in (("reference", 6.2), ("at_15", 6.7056), ("contrast", 7.2)):
        build(suffix, speed)
