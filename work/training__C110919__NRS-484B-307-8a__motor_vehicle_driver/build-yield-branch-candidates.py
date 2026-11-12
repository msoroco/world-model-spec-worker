"""Materialize eight unselected exact C110919 pedestrian-conflict bundles."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
OUT = HERE / "yield_branch_cases"
FILES = {
    "runner.py": "yield_branch_runner.py",
    "finalize.py": "yield_branch_finalize.py",
    "yield_branch.py": "yield_branch.py",
    "geometry.py": "geometry.py",
    "variant_geometry.py": "variant_geometry.py",
    "controller.py": "controller.py",
    "engineering.py": "engineering.py",
    "measure.py": "measure.py",
    "cameras.py": "cameras.py",
    "tests/test_native.py": "test_native.py",
    "tests/test_yield_branch.py": "test_yield_branch.py",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    spec = importlib.util.spec_from_file_location("c110919_engineering", NATIVE / "engineering.py")
    engineering = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engineering)
    template = json.loads((NATIVE / "config.json").read_text())
    dispositions = json.loads((HERE / "case-plan.json").read_text())["requirement_dispositions"]
    contents = {target: (NATIVE / source).read_text() for target, source in FILES.items()}
    recording = {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                              "method": "Retained Native actor, full-body, walker, signal and map readback joined to original frames",
                              "time_window": "entire 24 s / 480-frame attempt",
                              "reference_frame": "surveyed Native intersection and exact original frame identity",
                              "uncertainty": "50 ms sampling; pedestrian signal direction and pixels require independent review"}
                             for name in template["mandatory_channels"]],
                 "context_inputs": [],
                 "limitations": ["CPU diagnostics do not prove original pedestrian timing, video visibility or legal right-of-way"]}
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name, "status": "draft_yield_branch_not_selected",
                "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
                "cases": []}
    for suffix in ("yield_wait", "yield_conflict_entry"):
        case_id = HERE.name + "__" + suffix
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": index,
                                      "requirement": dispositions[index]["requirement"],
                                      "source": dispositions[index]["source"],
                                      "output_key": key, "method": method,
                                      "value_type": "object", "kind": "measured",
                                      "inputs": inputs}
                                     for index, key, method, inputs in
                                     ((0, "steady_red_activation", "measure_signal",
                                       ["native_samples.jsonl", "road_geometry.json"]),
                                      (2, "pedestrian_conflict_branch", "measure_yield_branch",
                                       ["native_samples.jsonl"]),
                                      (3, "right_turn_stop", "measure_stop",
                                       ["native_samples.jsonl", "road_geometry.json"]))],
                    "negative": {"remove": ["road_geometry.json"],
                                 "error_contains": "Missing required source: road_geometry.json"}}
        contract_path = OUT / suffix / "measurement-contract.json"
        save(contract_path, contract)
        entry = {"case_id": case_id, "kind": "draft_not_selected",
                 "candidate_risk": {"status": "physical",
                                    "reason": "Original red stop, pedestrian signal direction, full-body overlap and four-camera pixels require Native review"},
                 "measurement_contract": str(contract_path.relative_to(HERE)),
                 "measurement_procedure": {"entrypoint": "finalize.py",
                                           "output_schema": "c110919-saved-analysis-v1"},
                 "candidates": []}
        for candidate in engineering.CANDIDATES:
            config = dict(template)
            config.update(case_id=case_id, selected_case_id=case_id,
                          case_suffix=suffix, candidate_id=candidate,
                          knobs=engineering.parameters("reference", candidate)["knobs"],
                          supported_case_ids=[case_id], case={"case_id": case_id},
                          source_packets=[], recording_description=recording,
                          cameras=[{"name": name, "width": width, "height": height}
                                   for name, width, height in
                                   (("overview", 1920, 1080), ("approach", 1280, 720),
                                    ("reference_corner", 1280, 720),
                                    ("driver_reference", 1280, 720))])
            construction = {"case_id": case_id, "cell_id": "C110919",
                            "law_id": "NRS-484B-307-8a", "actor": "motor_vehicle_driver",
                            "entrypoint": "runner.py",
                            "files": [{"path": target, "content": content}
                                      for target, content in contents.items()] +
                                     [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}],
                            "recording_description": recording,
                            "mechanisms": ["authored marked stop line and two-directional receiving road",
                                           "shared full-body red stop before pedestrian conflict comparison",
                                           "walker actor and four synchronized lossless source cameras"],
                            "termination_rules": ["exact 480 original frames",
                                                  "capture and restoration errors retained"],
                            "status": "unselected_cpu_draft"}
            path = OUT / suffix / candidate / "construction.json"
            save(path, construction)
            ref = {"id": candidate, "construction": str(path.relative_to(HERE)),
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update({key: ref[key] for key in
                              ("construction", "construction_sha256")})
            else:
                trigger = engineering.TRIGGERS[candidate]
                ref.update(trigger={"source": trigger["source"],
                                    "metric": trigger["metric"],
                                    "failure_condition": f"{trigger['op']} {trigger['threshold']}"},
                           changed_knobs=list(engineering.CHANGES[candidate]))
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    path = HERE / "draft-yield-branch-execution-manifest.json"
    save(path, manifest)
    print(json.dumps({"cases": 2, "candidate_bundles": 8,
                      "manifest_sha256": sha(path), "selected": False}))


if __name__ == "__main__":
    main()
