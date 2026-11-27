"""Materialize two exact-case bundles and their source-bound measurement plan."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = ("prompt_brake", "deferred_brake")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    proposals = json.loads((ROOT / "proposals/cases.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base_scene = json.loads((ROOT / "scene.json").read_text())
    manifest_path = ROOT / "execution-manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"cases": []}
    old_cases = {item["case_id"]: item for item in previous["cases"]}
    manifest = {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"), "cases": []}
    disposition = plan["requirement_dispositions"][0]
    contract = {"format": "worker-measurement-contract",
                "requirements": [{"disposition_index": 0,
                                  "requirement": disposition["requirement"],
                                  "source": disposition["source"],
                                  "output_key": "pedestrian_on_road_caution_measurement",
                                  "method": "measure", "value_type": "object", "kind": "measured",
                                  "inputs": ["road-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl"]}],
                "negative": {"remove": ["encounter-history.jsonl"],
                             "error_contains": "Missing required source: encounter-history.jsonl"}}
    write(ROOT / "measurement-contract.json", contract)
    source_files = ("runner.py", "road_scene.py", "native_capture.py", "analysis.py",
                    "delivery_audit.py", "comparison_audit.py", "audit_probe.py",
                    "tests/test_road_scene.py", "tests/test_analysis.py",
                    "tests/test_native_capture.py", "tests/test_delivery_audit.py",
                    "tests/test_comparison_audit.py")
    for index, suffix in enumerate(CASES):
        cid = ROOT.name + "__" + suffix
        proposal = next(item for item in proposals["cases"] if item["case_id"] == cid)
        scene = dict(base_scene, case_id=cid, response_policy=suffix)
        config = {"assignment_id": ROOT.name, "selected_case_id": cid,
                  "supported_case_ids": [ROOT.name + "__" + item for item in CASES],
                  "law_id": "NRS-484B-280-1c", "cell_id": "C233871",
                  "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
                  "required_atoms": [], "source_packets": [],
                  "cameras": [{"name": name, "width": width, "height": height,
                               "pose_strategy": "fixed road encounter view" if name != "driver_reference" else "ego mounted",
                               "fov_deg": 90} for name, width, height in
                              (("overview", 1920, 1080), ("approach", 1280, 720),
                               ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
                  "case": {"case_id": cid, "response_policy": suffix,
                           "recording_description": proposal["recording_description"]},
                  "physical_completion": {"criterion": "travel_progress",
                                          "motion_source": "trace.jsonl", "position_key": "position_m",
                                          "minimum_progress_m": 5, "minimum_samples": 2,
                                          "engineering_tolerances_not_legal": True}}
        files = [{"path": name, "content": (ROOT / name).read_text()} for name in source_files]
        files.extend([{"path": "scene.json", "content": json.dumps(scene, indent=2) + "\n"},
                      {"path": "config.json", "content": json.dumps(config, indent=2, ensure_ascii=False) + "\n"}])
        construction = {"law_id": "NRS-484B-280-1c", "cell_id": "C233871",
                        "actor": "motor_vehicle_driver", "case_id": cid,
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": proposal["recording_description"],
                        "mechanisms": ["source-gated original OpenDRIVE road and no-sidewalk review",
                                       "separate motor vehicle and on-road pedestrian bodies",
                                       "instrumented scripted-driver observation input",
                                       "source-hashed saved encounter analysis"],
                        "measurement_plan": {"caution": "Original driver input, brake, speed, body gap and contact; legal judgment unresolved"},
                        "static_checks": ["ego approach intersects on-road pedestrian location",
                                          "road classification, edge and sidewalk source required"],
                        "termination_rules": ["stop after planned travel or physical failure"]}
        path = ROOT / "construction.json" if index == 0 else ROOT / "cases/deferred_brake/construction.json"
        write(path, construction)
        if index == 0:
            write(ROOT / "scene.json", scene)
            write(ROOT / "config.json", config)
        old = old_cases.get(cid, {})
        entry = {**old, "case_id": cid, "kind": "delivery",
                 "construction": str(path.relative_to(ROOT)), "construction_sha256": sha(path),
                 "measurement_contract": "measurement-contract.json",
                 "measurement_procedure": {"entrypoint": "analysis.py"},
                 "fixture_recipe": str((ROOT / ("diagnostic-" + suffix + "-recipe.json")).relative_to(REPO)),
                 "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                 "candidate_risk": {"status": "physical",
                                    "reason": "A Native map lane or pedestrian asset may not realize the authored on-road encounter or four-camera coverage."},
                 "candidates": old.get("candidates", []) if old.get("construction_sha256") == sha(path) else []}
        entry["acquisition"] = {item["name"]: {"entrypoint": "analysis.py",
            "method": "Original source-hashed on-road encounter projected by saved analyzer",
            "evidence": "channels/" + item["name"] + ".jsonl"}
            for item in proposal["recording_description"]["channels"]}
        entry["acquisition"].update({item["name"]: {"entrypoint": "analysis.py",
            "method": "Original OpenDRIVE road and driver-input context projection",
            "evidence": "channels/context.json"}
            for item in proposal["recording_description"]["context_inputs"]})
        if entry.get("offline", {}).get("construction_sha256") != entry["construction_sha256"]:
            for key in ("offline", "compatibility", "physical_preparation", "delivery_acceptance", "post_capture"):
                entry.pop(key, None)
        manifest["cases"].append(entry)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
