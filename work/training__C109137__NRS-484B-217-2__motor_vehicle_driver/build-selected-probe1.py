"""Build the first exact selected crossing compatibility diagnostic."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / "native/zone"
sys.path.insert(0, str(ZONE))
from prove_saved import fixture

CASE_ID = HERE.name + "__probe_1"
SOURCE = ZONE / "drafts/probe_1/primary"
DEST = HERE / "selected-probe1-fixture"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def jsonlines(values):
    return "".join(json.dumps(x, sort_keys=True, allow_nan=False) + "\n" for x in values)


def channel(name, unit, method):
    return {"name": name, "unit": unit, "method": method,
            "reference_frame": "original Native frame and time",
            "sampling_rate_hz": 20, "time_window": "600-frame crossing attempt",
            "uncertainty": "50 ms bracket; actual pixels and legal zone review pending"}


def main():
    scratch = ROOT / ".runtime-work/c109137-selected-probe1-source"
    raw_path, map_path, review_path = fixture(SOURCE, scratch)
    DEST.mkdir(exist_ok=True)
    shutil.copyfile(raw_path, DEST / "native-raw-actors.jsonl")
    raw = rows(raw_path)
    mapping = rows(map_path)
    for row in mapping:
        row["carla_frame"] = row["native_frame"]
    (DEST / "video_frames.jsonl").write_text(jsonlines(mapping))
    reviewed = json.loads(review_path.read_text())
    reviewed["video_frames_sha256"] = sha(DEST / "video_frames.jsonl")
    write(DEST / "review.json", reviewed)
    trace = []
    evidence = []
    graphs = []
    graph_frames = []
    for row in raw:
        i = row["frame"]
        native = row["native_frame"]
        t = row["time_s"]
        ego = row["ego"]
        center = ego["center_native_xyz_m"]
        velocity = ego["velocity_native_xyz_mps"]
        trace.append({"frame": native, "time_s": t,
                      "position": dict(zip(("x", "y", "z"), center)),
                      "position_m": center, "velocity_mps": velocity,
                      "speed_mps": ego["speed_mps"],
                      "speed_mph": ego["speed_mps"] * 2.2369362920544,
                      "heading_deg": ego["yaw_deg"],
                      "control": {"throttle": 0, "brake": 0, "hand_brake": False}})
        evidence.append({"actor_id": ego["actor_id"],
                         "original_frame": native, "replay_frame": native,
                         "recording_time_s": t, "replay_simulation_time_s": t,
                         "ego": {"body_vertices_m": ego["body_native_xyz_m"],
                                 "heading_deg": ego["yaw_deg"],
                                 "position_m": center, "speed_mps": ego["speed_mps"],
                                 "synthetic_diagnostic": True,
                                 "speed_provenance": "synthetic_native_sample"},
                         "participants": {name: row[name] for name in ("oncoming", "following")},
                         "world": {"road_projection": {"road_id": row["observed_road_id"],
                                                       "lane_id": row["observed_lane_id"],
                                                       "section_id": 0, "s_m": center[0]},
                                   "weather": {"cloudiness": 0, "fog_density": 0,
                                               "precipitation": 0, "wetness": 0}}})
        path = f"capture/native/graphs/base/{native:08d}.adapter.json"
        graphs.append({"path": path,
                       "attributes": {"frame": native, "simulation_time_s": t,
                                      "source": "C109137 synthetic crossing source",
                                      "synthetic_diagnostic": True},
                       "nodes": [{"id": "ego", "attributes": {
                           "entity_id": ego["actor_id"], "sem_class": "ego",
                           "vertex": center, "forward": [1.0, 0.0, 0.0],
                           "threedbbox": ego["body_native_xyz_m"]}}],
                       "edges": []})
        graph_frames.append({"frame": native, "simulation_time": t,
                             "adapter_graph": f"graphs/base/{native:08d}.adapter.json",
                             "base": f"graphs/base/{native:08d}.adapter.json",
                             "nodes": 1, "edges": 0})
    (DEST / "trace.jsonl").write_text(jsonlines(trace))
    (DEST / "capture").mkdir(exist_ok=True)
    (DEST / "capture/evidence.jsonl").write_text(jsonlines(evidence))
    write(DEST / "capture/manifest.json", {
        "synthetic_diagnostic": True, "extraction_confirmed": True,
        "frames": 600, "sources": {"trace.jsonl": sha(DEST / "trace.jsonl"),
                                   "road.xodr": sha(SOURCE / "zone-adjoining.xodr")}})
    videos = [{"path": name + ".mkv", "frames": 600,
               "width": 1920 if name == "overview" else 1280,
               "height": 1080 if name == "overview" else 720,
               "fps": 20, "color": "black"}
              for name in ("overview", "approach", "reference_corner", "driver_reference")]
    spec = {"files": {"capture/native/frames.jsonl": jsonlines(graph_frames),
                      "capture/recorder_info.txt": "synthetic CPU crossing diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n"},
            "graphs": graphs, "videos": videos}
    spec_path = HERE / "selected-probe1-fixture-spec.json"
    write(spec_path, spec)
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": str(p.relative_to(DEST)),
                           "source": str(p.relative_to(ROOT)), "sha256": sha(p)}
                          for p in sorted(DEST.rglob("*")) if p.is_file()],
              "generator": {"source": str(spec_path.relative_to(ROOT)),
                            "sha256": sha(spec_path)}}
    recipe["sources"].append({"path": "road.xodr",
                              "source": str((SOURCE / "zone-adjoining.xodr").relative_to(ROOT)),
                              "sha256": sha(SOURCE / "zone-adjoining.xodr")})
    recipe_path = HERE / "selected-probe1-fixture-recipe.json"
    write(recipe_path, recipe)
    description = {"channels": [
        channel("stripe_body_crossing", "object", "Native ego body versus authored stripe"),
        channel("adjoining_road_entry", "object", "Native waypoint road/lane readback"),
        channel("prior_left_indicator", "object", "Native observed vehicle light state"),
        channel("oncoming_following_traffic", "object", "Native other-actor bodies and velocities")],
        "context_inputs": [],
        "limitations": ["Authored zone designation and synthetic pixels cannot establish physical or legal outcome"]}
    construction = json.loads((ZONE / "runtime-drafts/probe_1/primary/construction.json").read_text())
    config = json.loads(next(x["content"] for x in construction["files"] if x["path"] == "config.json"))
    config.update({"cell_id": "C109137", "law_id": "NRS-484B-217-2",
                   "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
                   "selected_case_id": CASE_ID, "supported_case_ids": [CASE_ID],
                   "required_atoms": [], "source_packets": [],
                   "case": {"case_id": CASE_ID}, "recording_description": description,
                   "cameras": [{"name": v["path"].removesuffix(".mkv"),
                                "width": v["width"], "height": v["height"],
                                "fov_deg": 90, "pose_strategy": "authored crossing source view"}
                               for v in videos]})
    for item in construction["files"]:
        if item["path"] == "config.json":
            item["content"] = json.dumps(config, indent=2, allow_nan=False) + "\n"
        elif item["path"] == "capture.py":
            item["content"] = (item["content"]
                .replace('("forward", 1280', '("approach", 1280')
                .replace('("stripe_side", 1280', '("reference_corner", 1280')
                .replace('("rear", 1280', '("driver_reference", 1280')
                .replace('name == "rear"', 'name == "driver_reference"')
                .replace('("forward", "rear")', '("approach", "driver_reference")'))
        elif item["path"] == "saved.py":
            item["content"] = item["content"].replace(
                "CAMERAS = ('overview', 'forward', 'stripe_side', 'rear')",
                "CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')")
    construction["files"].append({"path": "finalize.py",
                                  "content": (ZONE / "selected_finalize.py").read_text()})
    construction["recording_description"] = description
    construction["status"] = "selected_diagnostic_pending_proofs"
    selected_path = HERE / "selected-probe1-construction.json"
    write(selected_path, construction)
    disposition = json.loads((HERE / "case-plan.json").read_text())["requirement_dispositions"][0]
    contract = {"format": "worker-measurement-contract", "case_id": CASE_ID,
                "requirements": [{"disposition_index": 0,
                                  "requirement": disposition["requirement"],
                                  "source": disposition["source"],
                                  "kind": "measured", "method": "measure_adjoining_crossing",
                                  "output_key": "adjoining_crossing", "value_type": "object",
                                  "inputs": list(("native-raw-actors.jsonl", "video_frames.jsonl",
                                                  "review.json", "trace.jsonl", "capture/evidence.jsonl"))}],
                "negative": {"remove": ["native-raw-actors.jsonl"],
                             "error_contains": "Missing required source: native-raw-actors.jsonl"},
                "status": "selected_diagnostic_pending_proofs"}
    write(HERE / "selected-probe1-measurement-contract.json", contract)
    proposal_path = HERE / "proposals/cases.json"
    previous = json.loads(proposal_path.read_text()) if proposal_path.is_file() else {"cases": []}
    cases = {item["case_id"]: item for item in previous["cases"]}
    cases[CASE_ID] = {"case_id": CASE_ID, "recording_description": description}
    write(proposal_path, {"actor": "motor_vehicle_driver", "cell_id": "C109137",
                          "status": "draft", "sweep_specs": [],
                          "cases": [cases[key] for key in sorted(cases)]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "status": "selected_diagnostic_pending_proofs", "delivery_ready": False,
                "original_native_observed": False,
                "cases": [{"case_id": CASE_ID, "id": "primary", "kind": "delivery",
                           "construction": selected_path.name,
                           "construction_sha256": sha(selected_path),
                           "candidates": [],
                           "fixture_recipe": str(recipe_path.relative_to(ROOT)),
                           "measurement_contract": "selected-probe1-measurement-contract.json",
                           "measurement_procedure": {"entrypoint": "finalize.py"}}]}
    write(HERE / "selected-probe1-manifest.json", manifest)
    print(json.dumps({"case_id": CASE_ID, "construction_sha256": sha(selected_path),
                      "fixture_spec_sha256": sha(spec_path)}))


if __name__ == "__main__":
    main()
