"""Build seven source-bound selected constructions for pinned CPU proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCES = ("runner.py", "emergency_scene.py", "native_scene.py",
           "native_capture.py", "actor_readback.py", "camera_recorder.py",
           "device_readback.py", "original_adapters.py", "native_handoff.py",
           "native_camera_rig.py", "saved_finalizer.py", "warning_audit.py",
           "pixel_audit.py", "physical_audit.py", "delivery_audit.py",
           "comparison_audit.py", "case-plan.json")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    proposals = json.loads((HERE / "proposals/cases.json").read_text())
    semantic = {case["case_id"]: case for case in proposals["cases"]
                if case["target_type"] != "baseline"}
    if set(semantic) != {case["case_id"] for case in plan["cases"]}:
        raise ValueError("Canonical proposal and exact case plan differ")
    tests = tuple(sorted(path.relative_to(HERE).as_posix() for path in
                         (HERE / "tests").glob("test_*.py")
                         if path.name != "test_semantic_proposals.py"))
    rows = []
    first = None
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        if suffix == case_id:
            raise ValueError("Foreign case")
        config = {"assignment_id": HERE.name, "selected_case_id": case_id,
                  "law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "rate_hz": 20, "duration_s": 45,
                  "frame_count": 900,
                  "cameras": [{"name": name, "width": width, "height": height,
                               "pose_strategy": "reviewed original Native site and fixed rig",
                               "fov_deg": 90} for name, width, height in CAMERAS],
                  "required_atoms": [], "source_packets": [],
                  "required_sources": ["site_packet", "dispatch_context",
                                       "equipment_record", "device_samples", "camera_media"],
                  "case": {"case_id": case_id, "event": case["authored_event_context"],
                           "siren": case["requested_siren"],
                           "lamps": case["requested_warning_lamps"]},
                  "supported_case_ids": [c["case_id"] for c in plan["cases"]],
                  "physical_acceptance_claimed": False}
        files = [{"path": name, "source": (HERE / name).relative_to(REPO).as_posix(),
                  "content": (HERE / name).read_text()} for name in SOURCES + tests]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {"case_id": case_id, "law_id": plan["law_id"],
                        "cell_id": plan["cell_id"], "actor": plan["actor"],
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": semantic[case_id]["recording_description"],
                        "measurement_plan": {"entrypoint": "saved_finalizer.py",
                                             "sources": ["capture_receipt.json",
                                                         "device_trace.jsonl", "actor_trace.jsonl",
                                                         "camera_trace.jsonl", "site_packet.json"],
                                             "case_id": case_id},
                        "static_checks": ["exact source document and case identity",
                                          "900 contiguous original Native frames"],
                        "termination_rules": ["900 Native ticks maximum",
                                              "stop on source, frame or restoration error"],
                        "mechanisms": ["source-gated emergency-device Native approach",
                                       "four original RGB views and saved-only audit"],
                        "status": "partial: source review and full CPU receipts pending"}
        target = HERE / "constructions" / (suffix + ".json")
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + "\n")
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Returned construction too large")
        if first is None:
            first = construction
            (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n")
            (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
        definitions = (
            ("response_warning_observation", ["device_trace.jsonl", "actor_trace.jsonl", "dispatch_context.json"]),
            ("pursuit_warning_observation", ["device_trace.jsonl", "dispatch_context.json"]),
            ("temporal_siren_relation", ["device_trace.jsonl", "dispatch_context.json"]),
            ("lamp_without_siren_observation", ["device_trace.jsonl", "equipment_record.json"]),
            ("equipment_authorization_record", ["equipment_record.json", "device_trace.jsonl"]),
        )
        selected = [index for index, disposition in enumerate(plan["requirement_dispositions"])
                    if disposition["status"] == "selected_required" and
                    case_id in disposition.get("case_ids", [])]
        contract = {"format": "worker-measurement-contract",
                    "requirements": [{"disposition_index": index,
                                      "requirement": plan["requirement_dispositions"][index]["requirement"],
                                      "source": plan["requirement_dispositions"][index]["source"],
                                      "output_key": definitions[index][0],
                                      "method": "measure", "value_type": "object",
                                      "kind": "measured", "inputs": definitions[index][1]}
                                     for index in selected],
                    "negative": {"remove": ["device_trace.jsonl"],
                                 "error_contains": "Missing required source: device_trace.jsonl"}}
        contract_path = HERE / "measurements" / (suffix + ".json")
        contract_path.parent.mkdir(exist_ok=True)
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        rows.append({"case_id": case_id, "kind": "delivery",
                     "construction": target.relative_to(HERE).as_posix(),
                     "construction_sha256": sha(target),
                     "measurement_contract": contract_path.relative_to(HERE).as_posix(),
                     "measurement_procedure": {"entrypoint": "saved_finalizer.py"},
                     "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                        "host_env_var": "CARLA_HOST",
                                        "port_env_var": "CARLA_PORT"},
                     "candidate_risk": case["candidate_risk"],
                     "status": "partial_cpu_receipts_pending"})
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": rows, "status": "partial_cpu_receipts_pending"}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("built seven exact selected constructions and partial canonical manifest")


if __name__ == "__main__":
    main()
