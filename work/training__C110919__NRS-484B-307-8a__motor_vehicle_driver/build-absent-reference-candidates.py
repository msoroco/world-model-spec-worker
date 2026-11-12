"""Build eight unselected Native bundles for the no-reference right-turn pair."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
SOURCES = {name: name for name in ("runner.py", "geometry.py", "variant_geometry.py",
                                  "controller.py", "engineering.py", "measure.py",
                                  "cameras.py", "finalize.py")}
SOURCES["tests/test_native.py"] = "test_native.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    spec = importlib.util.spec_from_file_location("c110919_variant_engineering", NATIVE / "engineering.py")
    engineering = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engineering)
    template = json.loads((NATIVE / "config.json").read_text())
    recording = {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                               "method": "Retained Native actor, body, signal and map readback joined to original frames",
                               "time_window": "entire 24 s / 480-frame attempt",
                               "reference_frame": "surveyed Native intersection map and original frame identity",
                               "uncertainty": "50 ms sampling; physical stopping-reference absence and pixels require independent review"}
                              for name in template["mandatory_channels"]],
                 "context_inputs": [],
                 "limitations": ["CPU fixtures do not prove absence in original Native map/pixels or accepted recording"]}
    files = {target: (NATIVE / source).read_text() for target, source in SOURCES.items()}
    dispositions = json.loads((HERE / "case-plan.json").read_text())["requirement_dispositions"]
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name, "status": "draft_absent_reference_not_selected",
                "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
                "cases": []}
    for suffix in ("absent_reference", "absent_reference_contrast"):
        case_id = HERE.name + "__" + suffix
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": i,
                                      "requirement": dispositions[i]["requirement"],
                                      "source": dispositions[i]["source"],
                                      "output_key": key, "method": method,
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["native_samples.jsonl", "road_geometry.json"]}
                                     for i, key, method in ((0, "steady_red_activation", "measure_signal"),
                                                            (1, "right_turn_stop", "measure_stop"),
                                                            (2, "right_turn_yield", "measure_turn_yield"),
                                                            (3, "right_turn_stop", "measure_stop"))],
                    "negative": {"remove": ["road_geometry.json"],
                                 "error_contains": "Missing required source: road_geometry.json"}}
        contract_path = HERE / "absent-reference-candidates" / suffix / "measurement-contract.json"
        save(contract_path, contract)
        entry = {"case_id": case_id, "kind": "draft_not_selected",
                 "candidate_risk": {"status": "physical",
                                    "reason": "Original absence of crosswalk/sign/marking, intersection boundary, signal, body and pixels require Native evidence"},
                 "measurement_contract": str(contract_path.relative_to(HERE)),
                 "measurement_procedure": {"entrypoint": "finalize.py",
                                           "output_schema": "c110919-saved-analysis-v1"},
                 "candidates": []}
        for candidate in engineering.CANDIDATES:
            config = dict(template)
            config.update(case_id=case_id, selected_case_id=case_id, case_suffix=suffix,
                          candidate_id=candidate,
                          knobs=engineering.parameters(suffix, candidate)["knobs"],
                          supported_case_ids=[case_id], case={"case_id": case_id},
                          source_packets=[], recording_description=recording,
                          cameras=[{"name": name, "width": width, "height": height}
                                   for name, width, height in (("overview", 1920, 1080),
                                                               ("approach", 1280, 720),
                                                               ("reference_corner", 1280, 720),
                                                               ("driver_reference", 1280, 720))])
            construction = {"case_id": case_id, "cell_id": "C110919",
                            "law_id": "NRS-484B-307-8a", "actor": "motor_vehicle_driver",
                            "entrypoint": "runner.py",
                            "files": [{"path": target, "content": content} for target, content in files.items()] +
                                     [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}],
                            "recording_description": recording,
                            "mechanisms": ["authored OpenDRIVE lacks approach crosswalk and stop marking",
                                           "observed-pose right-turn controller stops before intersection boundary when requested",
                                           "pedestrian actor and four synchronized lossless cameras"],
                            "termination_rules": ["exact 480 original frames", "capture and restoration errors retained"],
                            "status": "unselected_cpu_draft"}
            path = HERE / "absent-reference-candidates" / suffix / candidate / "construction.json"
            save(path, construction)
            ref = {"id": candidate, "construction": str(path.relative_to(HERE)),
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update({key: ref[key] for key in ("construction", "construction_sha256")})
            else:
                trigger = engineering.TRIGGERS[candidate]
                ref.update(trigger={"source": trigger["source"], "metric": trigger["metric"],
                                    "failure_condition": f"{trigger['op']} {trigger['threshold']}"},
                           changed_knobs=list(engineering.CHANGES[candidate]))
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    path = HERE / "draft-absent-reference-execution-manifest.json"
    save(path, manifest)
    print(json.dumps({"cases": len(manifest["cases"]), "candidate_bundles": 8,
                      "manifest_sha256": sha(path), "selected": False}))


if __name__ == "__main__":
    main()
