"""Build source-shaped CPU diagnostic inputs; never original alley evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from selected_plan import ASSIGNMENT, CASES, CELL, SOURCE_KEYS


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = HERE.parents[2]
EXAMPLE = json.loads((REPO / "runtime/fixtures/example.json").read_text())
VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n")


def json_write(path, content):
    write(path, json.dumps(content, separators=(",", ":")))


def video_hashes(scratch):
    scratch.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, width, height in VIEWS:
        path = scratch / (name + ".mkv")
        if not path.is_file():
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel",
                "error", "-n", "-f", "lavfi", "-i",
                f"color=c=black:s={width}x{height}:r=20", "-frames:v", "600",
                "-an", "-c:v", "ffv1", "-threads", "1", "-fflags", "+bitexact",
                "-flags:v", "+bitexact", str(path)], check=True, timeout=300)
        result[name] = sha(path)
    return result


def build_one(case_id, video_sha):
    suffix = case_id.rsplit("__", 1)[-1]
    root = PACKAGE / "native" / "diagnostic" / suffix
    sources = root / "sources"
    survey = {key: "diagnostic:" + key for key in SOURCE_KEYS}
    survey.update(source_kind="original_native_alley_survey", fixed_cell=CELL,
        ordinance_status="unknown", reviewer="diagnostic-site-fixture",
        reviewed_source_sha256="synthetic-site-fixture-only",
        spawn_xyz_yaw_deg=[0, 0, 0, 0], park_xyz_m=[1, 0, 0],
        goods_origin_xyz_m=[1, 1, 0], goods_destination_xyz_m=[2, 1, 0],
        vehicle_blueprint="vehicle.diagnostic", goods_blueprint="static.prop.diagnostic")
    json_write(sources / "site-survey.json", survey)
    requested = CASES[case_id]
    event = requested["goods_motion_frame"]
    review = {"source_kind": "independent_original_video_review",
        "diagnostic_fixture_only": True, "case_id": case_id,
        "reviewer": "diagnostic-video-fixture", "full_interval_reviewed": True,
        "video_sha256": video_sha,
        "observed_event_ids": [] if event is None else ["diagnostic-goods-event"],
        "observed_event_frames": {} if event is None else
            {"diagnostic-goods-event": event},
        "observed_door_open_frame_ids": [],
        "commercial_classification_source_id": "diagnostic-classification",
        "commercial_classification_observed": False,
        "vehicle_within_alley_frame_ids": list(range(600))}
    json_write(sources / "goods-review.json", review)
    write(sources / "road.xodr", EXAMPLE["files"]["road.xodr"])
    write(sources / "carla_recorder.log",
          "Synthetic C378809 diagnostic recorder stand-in; no Native run.")
    write(sources / "capture/native_map_facts.json",
          EXAMPLE["files"]["capture/native_map_facts.json"])
    write(sources / "capture/recorder_info.txt",
          "Synthetic C378809 diagnostic; no Native recording.\n"
          "Create 205: vehicle.tesla.model3 (0) at (0, 0, 0)")
    base_trace = json.loads(EXAMPLE["files"]["trace.jsonl"].splitlines()[0])
    base_evidence = json.loads(EXAMPLE["files"]["capture/evidence.jsonl"].splitlines()[0])
    frame_rows, trace_rows, native_rows, evidence_rows, graph_rows = [], [], [], [], []
    source_ego = next(node for node in EXAMPLE["graphs"][0]["nodes"]
                      if node["id"] == "ego")
    keep = ("vertex", "sem_class", "forward", "right", "up", "entity_id",
            "threedbbox", "carla_vel_x", "carla_vel_y", "carla_vel_z",
            "carla_speed", "original_observation")
    ego = {"id": "ego", "attributes": {key: source_ego["attributes"][key]
                                        for key in keep}}
    for index in range(600):
        native_frame = 1000 + index
        t = index / 20
        frame_rows.append({"video_frame": index, "carla_frame": native_frame,
                           "native_frame": native_frame, "time_s": t})
        native_rows.append({"source_kind": "original_native_observation",
            "diagnostic_fixture_only": True, "case_id": case_id,
            "frame": index, "native_frame": native_frame, "t_s": t,
            "vehicle_id": 7,
            "alley_boundary_source_id": survey["alley_boundary_source_id"],
            "position_xyz_m": [1, 0, 0], "velocity_xyz_mps": [0, 0, 0],
            "goods_prop_motion_requested": event == index,
            "original_goods_transfer_verified": False})
        trace = copy.deepcopy(base_trace)
        trace["frame"] = native_frame
        trace["time_s"] = t
        trace["position_m"] = [1, 0, 0]
        trace["position"] = {"x": 1, "y": 0, "z": 0}
        trace["velocity_mps"] = [0, 0, 0]
        trace["speed_mps"] = 0
        trace["speed_mph"] = 0
        trace_rows.append(trace)
        evidence = copy.deepcopy(base_evidence)
        evidence["original_frame"] = native_frame
        evidence["replay_frame"] = native_frame
        evidence["recording_time_s"] = t
        evidence["replay_simulation_time_s"] = t
        evidence["ego"]["position_m"] = [1, 0, 0]
        evidence["ego"]["speed_mps"] = 0
        evidence["original_observations"]["rgb_sensors"] = [{
            "actor_id": 999, "blueprint": "sensor.camera.rgb",
            "diagnostic_fixture_only": True}]
        evidence["original_observations"]["frame"] = native_frame
        evidence["original_observations"]["time_s"] = t
        evidence["original_observations"]["participants"] = []
        evidence["original_observations"]["participant_inventory"] = []
        evidence["original_observations"]["world_settings"]["no_rendering_mode"] = False
        evidence_rows.append(evidence)
        graph_rows.append({"path": f"capture/native/graphs/base/{index:08d}.adapter.json",
            "attributes": {"frame": native_frame, "simulation_time_s": t,
                           "observed_evidence": evidence["original_observations"],
                           "synthetic_diagnostic": True},
            "nodes": [ego], "edges": []})
    for relative, rows in (("video_frames.jsonl", frame_rows),
                           ("alley-native.jsonl", native_rows),
                           ("trace.jsonl", trace_rows),
                           ("capture/evidence.jsonl", evidence_rows)):
        write(sources / relative, "\n".join(json.dumps(row, separators=(",", ":"))
                                             for row in rows))
    write(sources / "capture/native/frames.jsonl", "\n".join(json.dumps({
        "frame": 1000 + index, "simulation_time": index / 20,
        "adapter_graph": f"graphs/base/{index:08d}.adapter.json",
        "base": f"graphs/base/{index:08d}.adapter.json", "nodes": 1, "edges": 0},
        separators=(",", ":")) for index in range(600)))
    manifest = json.loads(EXAMPLE["files"]["capture/manifest.json"])
    manifest.update(case_id=case_id, frames=600,
                    required_observations=["kin.position", "kin.speed"],
                    source_run="synthetic:c378809-diagnostic-only",
                    extraction_confirmed=True,
                    sources={"road.xodr": sha(sources / "road.xodr"),
                             "trace.jsonl": sha(sources / "trace.jsonl"),
                             "carla_recorder.log": sha(sources / "carla_recorder.log")})
    manifest["native_map_facts"] = {
        "path": "native_map_facts.json",
        "sha256": sha(sources / "capture/native_map_facts.json")}
    json_write(sources / "capture/manifest.json", manifest)
    spec = {"files": {}, "graphs": graph_rows,
            "videos": [{"path": name + ".mkv", "frames": 600,
                        "width": width, "height": height,
                        "fps": 20, "color": "black"}
                       for name, width, height in VIEWS]}
    json_write(root / "fixture-spec.json", spec)
    inventory = [{"path": str(path.relative_to(sources)),
                  "source": str(path.relative_to(REPO)), "sha256": sha(path)}
                 for path in sorted(sources.rglob("*")) if path.is_file()]
    recipe = {"format": "worker-fixture-recipe", "sources": inventory,
        "generator": {"source": str((root / "fixture-spec.json").relative_to(REPO)),
                      "sha256": sha(root / "fixture-spec.json")}}
    json_write(root / "fixture-recipe.json", recipe)
    return {"case_id": case_id, "source_files": len(inventory),
            "spec_bytes": (root / "fixture-spec.json").stat().st_size}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", required=True)
    args = parser.parse_args()
    video_sha = video_hashes(Path(args.scratch))
    print(json.dumps([build_one(case, video_sha) for case in CASES], sort_keys=True))
