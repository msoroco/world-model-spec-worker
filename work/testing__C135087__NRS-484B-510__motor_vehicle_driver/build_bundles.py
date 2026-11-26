"""Bind the three exact restricted-zone cases to source-gated Native bundles."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _content(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    cases = plan["cases"]
    expected = {"clear_before_entry", "entrant_during_loading", "entrant_after_exchange"}
    if {case["case_id"].removeprefix(ASSIGNMENT + "__") for case in cases} != expected:
        raise ValueError("frozen entrant comparison cases changed")
    if not plan.get("requirement_dispositions"):
        plan["requirement_dispositions"] = [{
            "status": "selected_required",
            "requirement": "NRS-484B-510 restricted-purpose entrant during actual passenger loading",
            "source": {"path": "inputs/" + ASSIGNMENT + "/assignment.json",
                       "sha256": _sha(REPO / "inputs" / ASSIGNMENT / "assignment.json")},
            "evidence_or_gap": "No accepted recording or original restricted-zone survey supplied",
            "case_ids": [case["case_id"] for case in cases]}]
        plan_path.write_text(_content(plan))
    code = ("runner.py", "analysis.py", "native_capture.py", "restricted_zone.py", "reviewed_site.py",
            "site_geometry.py", "native_adapter.py", "semantic_feasibility.py",
            "zone_audit.py", "saved_audit.py", "delivery_audit.py", "comparison_audit.py")
    entries = []
    for case in cases:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        config = {"assignment_id": ASSIGNMENT, "selected_case_id": case_id,
                  "law_id": "NRS-484B-510", "cell_id": "C135087",
                  "actor": "motor_vehicle_driver", "rate_hz": 20,
                  "frame_count": 900, "duration_s": 45,
                  "required_atoms": [], "source_packets": [],
                  "supported_case_ids": sorted(c["case_id"] for c in cases),
                  "scenario_parameters": case["scenario_parameters"],
                  "cameras": [{"name": name, "width": width, "height": height,
                               "fov_deg": 75,
                               "pose_strategy": "review sign, zone, entrant access and passenger door"}
                              for name, width, height in CAMERAS]}
        files = [{"path": "config.json", "content": _content(config)}]
        files += [{"path": name, "content": (ROOT / name).read_text()} for name in code]
        files.append({"path": "tests/test_bundle.py",
                      "content": (ROOT / "tests/test_bundle.py").read_text()})
        construction = {"case_id": case_id, "law_id": "NRS-484B-510",
                        "cell_id": "C135087", "actor": "motor_vehicle_driver",
                        "candidate_id": "primary", "entrypoint": "runner.py",
                        "files": files,
                        "measurement_plan": {"case_id": case_id,
                                             "original_frames": 900,
                                             "measurements": ["passenger_exchange_state",
                                                              "entrant_approach_waiting_access",
                                                              "subject_zone_dwell",
                                                              "reviewed_zone_authority"],
                                             "legal_judgment": "unresolved"},
                        "recording_description": {
                            "channels": [{"name": name, "unit": unit,
                                          "method": method,
                                          "sampling_rate_hz": 20,
                                          "time_window": "45-second original Native trace",
                                          "reference_frame": "source-reviewed restricted zone",
                                          "uncertainty": "physical realization unverified"}
                                         for name, unit, method in (
                                             ("subject_zone_dwell", "s", "original subject position and speed"),
                                             ("passenger_exchange", "state", "original passenger boarding-state transition"),
                                             ("entrant_access", "state", "original entrant parking task, approach, waiting and blockage"))],
                            "context_inputs": [{"name": "reviewed_restricted_zone", "unit": "source record",
                                                "method": "ten independently reviewed site and actor source roles"}],
                            "limitations": ["No legal interference or temporary-duration cutoff inferred.",
                                            "Original site and Native footage require local review."]},
                        "mechanisms": ["source-reviewed restricted zone", "passenger-vehicle exchange",
                                       "restricted-purpose entrant route", "four original Native cameras"],
                        "static_checks": ["exact case and actor", "900 frames at 20 Hz",
                                          "four-camera pixel source", "ten reviewed source roles"],
                        "termination_rules": ["fail closed on missing original sources",
                                              "verify world restoration before seal"]}
        construction_path = ROOT / "cases" / suffix / "primary" / "construction.json"
        construction_path.parent.mkdir(parents=True, exist_ok=True)
        construction_path.write_text(_content(construction))
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": plan["requirement_dispositions"][0]["source"],
                                      "output_key": "restricted_zone_entrant_observations",
                                      "method": "build", "value_type": "object", "kind": "measured",
                                      "inputs": ["original-attempt/site-packet.json"]}],
                    "negative": {"remove": ["original-attempt/site-packet.json"],
                                 "error_contains": "Missing required source: original-attempt/site-packet.json"}}
        contract_path = ROOT / "cases" / suffix / "measurement-contract.json"
        contract_path.write_text(_content(contract))
        if suffix == "entrant_during_loading":
            (ROOT / "config.json").write_text(_content(config))
            (ROOT / "construction.json").write_text(_content(construction))
        entries.append({"case_id": case_id, "kind": "delivery", "diagnostic_only": True,
                        "construction": str(construction_path.relative_to(ROOT)),
                        "construction_sha256": _sha(construction_path),
                        "measurement_contract": str(contract_path.relative_to(ROOT)),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "acquisition": {
                            "subject_zone_dwell": {"entrypoint": "native_capture.py",
                                "method": "original subject position and speed with reviewed zone boundaries",
                                "evidence": ["original-attempt/history.jsonl", "original-attempt/context.json"]},
                            "passenger_exchange": {"entrypoint": "native_capture.py",
                                "method": "original passenger boarding-state transition and pixel citations",
                                "evidence": ["original-attempt/history.jsonl", "original-attempt/overview.zip"]},
                            "entrant_access": {"entrypoint": "native_capture.py",
                                "method": "original entrant parking task, approach, waiting and access readback",
                                "evidence": ["original-attempt/history.jsonl", "trace.jsonl", "video_frames.jsonl"]}},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/diagnostic-" + suffix + "-recipe.json",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": case["physical_risk_assessment"],
                        "candidates": []})
        output = REPO / ".runtime-work" / ("c135087-offline-" + suffix + "-nov26-v5")
        log = ROOT / ("cpu-offline-" + suffix + ".log")
        selection = output / "candidate-selection.json"
        if log.is_file() and selection.is_file():
            reported = json.loads(log.read_text())
            selected = json.loads(selection.read_text())
            if reported.get("case_id") == case_id and reported.get("offline_passed") is True and \
                    selected.get("construction_sha256") == _sha(construction_path):
                entries[-1]["offline"] = {
                    "command": (f".venv-cpu/bin/python runtime.py offline --manifest "
                                f"work/{ASSIGNMENT}/diagnostic-execution-manifest.json "
                                f"--case {case_id} --output .runtime-work/{output.name} "
                                f"--python {REPO}/.venv-cpu/bin/python"),
                    "exit_code": 0, "construction_sha256": _sha(construction_path),
                    "log": log.name, "log_sha256": _sha(log)}
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": _sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "diagnostic_only": True, "cases": entries}
    (ROOT / "diagnostic-execution-manifest.json").write_text(_content(manifest))
    (ROOT / "execution-manifest.json").write_text(_content(manifest))
    proposals = ROOT / "proposals"
    proposals.mkdir(exist_ok=True)
    (proposals / "cases.json").write_text(_content({
        "actor": "motor_vehicle_driver", "cell_id": "C135087",
        "semantic_status": "partial_stage_chain_pending",
        "cases": [{"case_id": entry["case_id"], "target_type": "selected",
                   "recording_description": json.loads((ROOT / entry["construction"]).read_text())
                       ["recording_description"]} for entry in entries]}))
    print("bound", len(entries), "source-gated restricted-zone constructions")


if __name__ == "__main__":
    main()
