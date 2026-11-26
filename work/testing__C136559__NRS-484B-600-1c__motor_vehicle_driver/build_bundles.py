"""Build eight exact, source-gated posted-speed offline bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from posted_site import CASES


ROOT = Path(__file__).resolve().parent
ID = ROOT.name


def content(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    planned = {case["case_id"] for case in plan["cases"]}
    if planned != {ID + "__" + case for case in CASES}:
        raise ValueError("frozen accepted case identities changed")
    cameras = [{"name": name, "width": width, "height": height,
                "fov_deg": 75, "pose_strategy": "review governed sign, ego passage and actual travel lane"}
               for name, width, height in (("overview", 1920, 1080),
                                           ("approach", 1280, 720),
                                           ("reference_corner", 1280, 720),
                                           ("driver_reference", 1280, 720))]
    common = ["runner.py", "posted_site.py", "analysis.py",
              "speed_source_review.py", "original_source_audit.py",
              "tests/test_posted_site.py"]
    entries = []
    for suffix in CASES:
        exact = ID + "__" + suffix
        variables = {
            "travel_direction": "opposite" if suffix == "opposite_direction" else "forward",
            "rate_relation": suffix if suffix in ("below", "equal", "above") else "above",
            "segment_mode": "outside" if suffix == "outside_zone" else "governed",
            "authority_mode": "non_authority" if suffix == "non_authority_sign" else "reviewed_public_authority",
            "unit_mode": "km/h" if suffix == "metric_equivalent" else "mph",
            "visibility_mode": "off_camera" if suffix == "sign_not_in_view" else "camera_review_required",
        }
        config = {"assignment_id": ID, "selected_case_id": exact,
                  "law_id": "NRS-484B-600-1c", "cell_id": "C136559",
                  "actor": "motor_vehicle_driver", "rate_hz": 20,
                  "frame_count": 900, "duration_s": 45, "cameras": cameras,
                  "supported_case_ids": sorted(planned), "required_atoms": [],
                  "source_packets": [], "case": {"case_id": exact,
                  "draft_variables": variables},
                  "control": {"requested_rate_relation": variables["rate_relation"],
                              "source": "engineering request, never a measured speed or legal threshold"}}
        files = [{"path": "config.json", "content": content(config)}]
        files += [{"path": name, "content": (ROOT / name).read_text()} for name in common]
        construction = {"case_id": exact, "law_id": "NRS-484B-600-1c",
                        "cell_id": "C136559", "actor": "motor_vehicle_driver",
                        "candidate_id": "primary", "entrypoint": "runner.py",
                        "files": files,
                        "measurement_plan": {"case_id": exact,
                                             "original_frames": 900,
                                             "measurements": ["actual_speed_mps", "posted_rate_mps",
                                                              "occupied_highway_segment", "travel_direction",
                                                              "public_authority_posting", "sign_visibility"],
                                             "legal_judgment": "unresolved"},
                        "recording_description": {
                            "channels": [{"name": "actual_speed_mps", "unit": "m/s",
                                          "method": "original Native vehicle motion at 20 Hz",
                                          "sampling_rate_hz": 20, "time_window": "full 45 seconds",
                                          "reference_frame": "original frame map",
                                          "uncertainty": "physical realization unverified"}],
                            "context_inputs": [{"name": "reviewed_posted_site", "unit": "source record",
                                                "method": "source-hashed public posting, direction and governed portion"}],
                            "limitations": ["No reviewed original site packet is in the frozen export.",
                                            "Requested speed is not measured speed."]},
                        "mechanisms": ["reviewed source-hashed posted sign and lane site",
                                       "four synchronized original Native camera views"],
                        "static_checks": ["exact case identity", "site provenance",
                                          "opposite lane identity", "45-second original frame contract"],
                        "termination_rules": ["900 original frames", "fail closed on absent reviewed site"]}
        path = ROOT / "cases" / suffix / "primary" / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content(construction))
        contract = {"format": "worker-measurement-contract", "case_id": exact,
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": plan["requirement_dispositions"][0]["source"],
                                      "output_key": "posted_speed_history", "method": "build",
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["original-attempt/posted-speed-source.json"]}],
                    "negative": {"remove": ["original-attempt/posted-speed-source.json"],
                                 "error_contains": "Missing required source: original-attempt/posted-speed-source.json"}}
        contract_path = ROOT / "cases" / suffix / "measurement-contract.json"
        contract_path.write_text(content(contract))
        entries.append({"case_id": exact, "kind": "delivery",
                        "diagnostic_only": True,
                        "construction": str(path.relative_to(ROOT)),
                        "construction_sha256": sha(path),
                        "measurement_contract": str(contract_path.relative_to(ROOT)),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": "work/" + ID + "/diagnostic-" + suffix + "-recipe.json",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "acquisition": {"actual_speed_mps": {"entrypoint": "analysis.py",
                                          "method": "source-sealed original vehicle motion",
                                          "evidence": "original-attempt/inventory.json"}},
                        "candidate_risk": {"status": "physical",
                                           "reason": "requested speed or sign visibility may not be realized on reviewed narrow-road geometry"},
                        "candidates": []})
        if suffix == "above":
            (ROOT / "config.json").write_text(content(config))
            (ROOT / "construction.json").write_text(content(construction))
    manifest = {"format": "worker-execution-manifest", "assignment_id": ID,
                "diagnostic_only": True, "status": "partial_source_gated",
                "cases": entries}
    (ROOT / "execution-manifest.json").write_text(content(manifest))
    print("built", len(entries), "exact source-gated posted-speed bundles")


if __name__ == "__main__":
    main()
