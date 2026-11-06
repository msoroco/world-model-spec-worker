"""Materializable exact, unselected Native bundles for six signaling cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
NATIVE = HERE / "native"
NAMES = ("primary", "fallback1", "fallback2", "fallback3")
SOURCES = ("runner.py", "geometry.py", "controller.py", "cameras.py", "engineering.py",
           "signal_control.py", "signal_measure.py", "fallback_triggers.py", "finalize.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    source_manifest = json.loads((HERE / "native-construction-manifest.json").read_text())
    requests = {(r["case_id"], r["candidate_id"]): r for r in source_manifest["candidates"]}
    common = {name: (NATIVE / name).read_text() for name in SOURCES}
    common["tests/test_bundle.py"] = (NATIVE / "test_bundle.py").read_text()
    recording = {"channels": [
        {"name": name, "unit": "structured", "sampling_rate_hz": 20,
         "method": "Retain original Native actor, map, indicator, controller and synchronized frame source; measurement requires saved verification",
         "time_window": "entire 40 s / 800-frame attempt", "reference_frame": "original Native frame and time",
         "uncertainty": "50 ms sampled state; physical and pixel review pending"}
        for name in ("sig.turn_indicator", "drv.distance_while", "kin.path_length",
                     "drv.turning", "env.precipitation", "kin.speed", "native_body_pose_control", "camera_frame_join")],
        "context_inputs": [{"name":"area_classification","unit":"categorical",
                            "method":"authored source context joined to surveyed Native map; physical area review pending"}],
        "limitations": ["Authored area context requires Native scene review", "Original indicator emission and pixels require physical review",
                        "No legal conclusion from synthetic or offline data"]}
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": plan["assignment_id"],
                "runtime_manifest_sha256": sha(REPO / "runtime/pipeline/SOURCE-MANIFEST.json"),
                "status": "draft_not_selected", "cases": []}
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        contract_rel = f"draft-candidates/{suffix}/measurement-contract.json"
        methods = {"text-0": ("continuous_signal_distance_ft", "measure_signal_distance", "number", "measured"),
                   "text-1": ("weather_context", "measure_weather_context", "text", "sourced_context"),
                   "reviewed-scope-0": ("other_area_coverage", "measure_other_area_coverage", "object", "sourced_context"),
                   "reviewed-scope-1": ("other_area_duplicate", "measure_other_area_duplicate", "object", "sourced_context")}
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id not in disposition.get("case_ids", []):
                continue
            key, method, value_type, kind = methods[disposition["requirement"]]
            requirements.append({"disposition_index": index, "requirement": disposition["requirement"],
                "source": disposition["source"], "output_key": key, "method": method,
                "value_type": value_type, "kind": kind,
                "inputs": ["native_samples.jsonl", "road_geometry.json"]})
        write(HERE / contract_rel, {"format": "worker-measurement-contract-v1", "case_id": case_id,
             "requirements": requirements,
             "negative": {"remove": ["native_samples.jsonl"],
                          "error_contains": "Missing required source: native_samples.jsonl"},
             "target_distance_ft": case["requested_setting"],
             "area": case["area_classification"], "rate_hz": 20, "duration_s": 40,
             "status": "unselected_contract_draft"})
        entry = {"case_id": case_id, "kind": "draft_not_selected",
                 "candidate_risk": {"status": "physical", "reason": "Original signal timing, tracking and pixel visibility require Native observation"},
                 "measurement_contract": contract_rel,
                 "measurement_procedure": {"entrypoint": "finalize.py", "status": "saved_source_diagnostic"},
                 "candidates": []}
        for candidate in NAMES:
            ref = requests[(case_id, candidate)]
            request = json.loads((REPO / ref["path"]).read_text())
            config = {"case_id": case_id, "selected_case_id": case_id,
                "candidate_id": candidate, "cell_id": plan["cell_id"], "law_id": plan["law_id"],
                "actor": plan["actor"], "rate_hz": 20, "duration_s": 40,
                "required_atoms": ["sig.turn_indicator", "drv.turning", "kin.speed"],
                "source_packets": [], "mandatory_channels": [x["name"] for x in recording["channels"]],
                "cameras": [{"name": name, "width": width, "height": height}
                            for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                                        ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
                "case": {"case_id": case_id}, "recording_description": recording,
                "native_request": request, "status": "unselected_native_runner_prototype"}
            files = [{"path": name, "content": content} for name, content in common.items()]
            files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
            construction = {"case_id": case_id, "cell_id": plan["cell_id"], "law_id": plan["law_id"],
                            "actor": plan["actor"], "entrypoint": "runner.py", "files": files,
                            "recording_description": recording,
                            "measurement_plan": {"method": "saved original indicator/path/turn interval", "status": "draft"},
                            "static_checks": ["owned extended OpenDRIVE", "prospective body containment",
                                              "exact request identity", "signal station and 40-second capture"],
                            "termination_rules": ["800 synchronized original Native frames", "retain failed capture and restore feedback"],
                            "status": "unselected_cpu_draft"}
            relative = f"draft-candidates/{suffix}/{candidate}/construction.json"
            path = HERE / relative
            write(path, construction)
            selected = {"id": candidate, "construction": relative, "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update(selected)
            else:
                failure = {"fallback1": ("runway_to_signal_onset_m", "below 12 m", "start_x_m -112 to -116"),
                           "fallback2": ("max_signal_window_route_error_m", "above 0.35 m", "target_speed_mps 5 to 4"),
                           "fallback3": ("signal_visibility_fraction", "below 95%", "approach camera height/FOV changed")}[candidate]
                selected.update(trigger={"source": "source-hashed original Native samples or reviewed source pixels",
                                         "metric": failure[0], "failure_condition": failure[1]},
                                changed_knobs=[failure[2]])
                entry["candidates"].append(selected)
        manifest["cases"].append(entry)
    write(HERE / "draft-execution-manifest.json", manifest)
    print(json.dumps({"cases": len(manifest["cases"]), "candidates": len(manifest["cases"]) * 4,
                      "status": manifest["status"]}))


if __name__ == "__main__":
    main()
