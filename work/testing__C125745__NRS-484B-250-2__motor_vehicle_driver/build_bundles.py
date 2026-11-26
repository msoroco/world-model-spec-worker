"""Build three exact source-gated median-opening timing bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
CAMERAS = [("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]


def content(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    cases = plan["cases"]
    if {case["case_id"].removeprefix(ASSIGNMENT + "__") for case in cases} != {
            "entry_below", "entry_inside", "entry_above"}:
        raise ValueError("frozen timing probe set changed")
    if not plan.get("requirement_dispositions"):
        plan["selected_branch"] = "Measured crossing-entry timing at a median-opening intersection."
        plan["requirement_dispositions"] = [{
            "status": "selected_required", "disposition_index": 0,
            "requirement": "Measure crossing-entry timing from two different highways at the median opening",
            "source": "inputs/" + ASSIGNMENT + "/assignment.json",
            "evidence_or_gap": "Accepted metadata lacks original entry footprints and official-device review",
            "case_ids": [case["case_id"] for case in cases]}]
        plan_path.write_text(content(plan))
    common = ["runner.py", "native_capture.py", "analysis.py", "entry_timing.py"]
    entries = []
    for case in cases:
        exact = case["case_id"]
        suffix = exact.removeprefix(ASSIGNMENT + "__")
        target = case["scenario_parameters"]["entry_time_difference_target_s"]
        config = {"assignment_id": ASSIGNMENT, "selected_case_id": exact,
                  "law_id": "NRS-484B-250-2", "cell_id": "C125745",
                  "actor": "motor_vehicle_driver", "rate_hz": 20,
                  "frame_count": 900, "duration_s": 45,
                  "supported_case_ids": sorted(c["case_id"] for c in cases),
                  "required_atoms": [], "source_packets": [],
                  "cameras": [{"name": name, "width": width, "height": height,
                               "fov_deg": 75,
                               "pose_strategy": "review both highway approaches, footprints and intersection boundary"}
                              for name, width, height in CAMERAS],
                  "case": {"case_id": exact, "timing_target_s": target,
                           "target_kind": suffix,
                           "official_device_status": "pending_source_review"}}
        files = [{"path": "config.json", "content": content(config)}]
        files.extend({"path": name, "content": (ROOT / name).read_text()} for name in common)
        files.append({"path": "tests/test_entry_timing.py",
                      "content": (ROOT / "test_entry_timing.py").read_text()})
        construction = {"case_id": exact, "law_id": "NRS-484B-250-2",
                        "cell_id": "C125745", "actor": "motor_vehicle_driver",
                        "candidate_id": "primary", "entrypoint": "runner.py", "files": files,
                        "measurement_plan": {"case_id": exact,
                                             "original_frames": 900,
                                             "measurements": ["ego_entry_bracket", "other_entry_bracket",
                                                              "ego_minus_other_entry_time_s",
                                                              "official_control_source", "left_right_priority_source"],
                                             "legal_judgment": "unresolved"},
                        "recording_description": {
                            "channels": [{"name": "intersection_entry_time_difference", "unit": "s",
                                          "method": "original 20 Hz body-footprint first intersection transitions",
                                          "sampling_rate_hz": 20, "time_window": "full 45 seconds",
                                          "reference_frame": "source-hashed intersection polygon",
                                          "uncertainty": "physical timing unverified"}],
                            "context_inputs": [{"name": "reviewed_median_opening_site", "unit": "source record",
                                                "method": "hash-reviewed map, highways, intersection and device authority"}],
                            "limitations": ["Official device and priority status require original source review.",
                                            "Timing target is not measured timing or a legal cutoff."]},
                        "mechanisms": ["two source-reviewed distinct highway approaches",
                                       "four synchronized Native camera views"],
                        "static_checks": ["exact timing case", "different highways",
                                          "intersection polygon source", "45-second clock"],
                        "termination_rules": ["900 contiguous original frames",
                                              "fail closed on absent reviewed site"]}
        path = ROOT / "cases" / suffix / "primary" / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content(construction))
        contract = {"format": "worker-measurement-contract", "case_id": exact,
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": plan["requirement_dispositions"][0]["source"],
                                      "output_key": "intersection_entry_time_difference",
                                      "method": "build", "value_type": "object", "kind": "measured",
                                      "inputs": ["original-attempt/entry-timing-source.json"]}],
                    "negative": {"remove": ["original-attempt/entry-timing-source.json"],
                                 "error_contains": "Missing required source: original-attempt/entry-timing-source.json"}}
        contract_path = ROOT / "cases" / suffix / "measurement-contract.json"
        contract_path.write_text(content(contract))
        entries.append({"case_id": exact, "kind": "delivery", "diagnostic_only": True,
                        "construction": str(path.relative_to(ROOT)),
                        "construction_sha256": sha(path),
                        "measurement_contract": str(contract_path.relative_to(ROOT)),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "physical",
                                           "reason": "source-reviewed median-opening geometry may not produce the requested entry ordering"},
                        "candidates": [],
                        "fixture_recipe": "work/" + ASSIGNMENT + "/diagnostic-" + suffix + "-recipe.json"})
        if suffix == "entry_inside":
            (ROOT / "config.json").write_text(content(config))
            (ROOT / "construction.json").write_text(content(construction))
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "partial_source_gated", "diagnostic_only": True,
                "cases": entries}
    (ROOT / "execution-manifest.json").write_text(content(manifest))
    print("built", len(entries), "exact timing constructions")


if __name__ == "__main__":
    main()
