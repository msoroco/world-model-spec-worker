"""Materialize nine exact, inline private-way Native construction drafts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from private_way_construction import ASSIGNMENT, CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE_FILES = ("runner.py", "native_operator.py", "native_acquisition.py",
                "finalize_native.py", "analysis.py", "private_way_site.py",
                "private_way_motion.py", "private_way_construction.py", "case-plan.json")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def make(case):
    variant = case["variant"]
    case_id = case["case_id"]
    maneuver, sides, policy = CASES[variant]
    cameras = [{"name": name, "width": 1920 if index == 0 else 1280,
                "height": 1080 if index == 0 else 720,
                "fov_deg": 75, "pose_strategy": "source-reviewed original private-way packet"}
               for index, name in enumerate(CAMERAS)]
    descriptions = {
        "private_way_ownership_and_access": "source-hashed private ownership and access records",
        "public_highway_status_and_boundary": "source-hashed public highway designation and boundary map",
        "entry_or_crossing_connection": "source-hashed connection and ego body progression",
        "all_highway_vehicle_approaches": "complete original Native highway actor inventory and motion",
        "ego_precedence_motion": "original Native ego body motion against highway approaches",
        "four_camera_original_pixels": "four original synchronized camera pixel streams",
    }
    recording = {
        "channels": [{"name": name, "unit": "source record", "sampling_rate_hz": 20,
                      "reference_frame": "original Native frame/time and reviewed map",
                      "time_window": "45-second original episode",
                      "method": description, "uncertainty": "original physical and legal review pending"}
                     for name, description in descriptions.items()],
        "context_inputs": [{"name": "reviewed_private_way_site_packet", "unit": "source record",
                            "method": "six source hashes and original OpenDRIVE map"}],
        "limitations": ["Requested control policy is an engineering target.",
                        "Original highway approach and legal yielding require independent review."],
    }
    config = {
        "assignment_id": ASSIGNMENT, "actor": "motor_vehicle_driver",
        "law_id": "NRS-484B-260", "cell_id": "C228096",
        "selected_case_id": case_id,
        "supported_case_ids": [ASSIGNMENT + "__" + name for name in CASES],
        "case": {"case_id": case_id, "recording_description": recording},
        "variant": variant, "maneuver": maneuver,
        "approach_sides": list(sides), "requested_control_policy": policy,
        "spawn_offset_m": 0.0,
        "duration_s": 45, "rate_hz": 20, "frame_count": 900,
        "cameras": cameras, "required_atoms": [], "source_packets": [],
        "diagnostic_only": True, "source_requirements": ["reviewed_private_way_site_packet"],
        "plan_sha256": _sha((ROOT / "case-plan.json").read_bytes()),
    }
    directory = ROOT / "cases" / variant
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(_json(config))
    files = []
    for name in SOURCE_FILES:
        source = ROOT / name
        files.append({"path": name, "source": str(source.relative_to(REPO)),
                      "content": source.read_text()})
    files.append({"path": "config.json", "content": _json(config)})
    test = '''"""Exact private-way inline import and identity contract."""\nimport json\nfrom pathlib import Path\nimport unittest\nimport runner\n\nclass BundleTest(unittest.TestCase):\n    def test_exact_identity(self):\n        root = Path(__file__).resolve().parents[1]\n        config = runner.check(root)\n        self.assertEqual(config["selected_case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])\n        self.assertEqual(config["frame_count"], 900)\n\nif __name__ == "__main__":\n    unittest.main()\n'''
    files.append({"path": "tests/test_bundle.py", "content": test})
    construction = {
        "case_id": case_id, "actor": "motor_vehicle_driver",
        "law_id": "NRS-484B-260", "cell_id": "C228096",
        "candidate_id": "primary", "entrypoint": "runner.py",
        "files": files, "recording_description": recording,
        "measurement_plan": {"procedure": "analysis.py", "contract":
                             "measurement-" + variant + ".json"},
        "mechanisms": ["source-hashed original private-way packet",
                       "actual Native actor and camera readback",
                       "saved-only source-bound measurement"],
        "static_checks": ["exact case identity", "six site source hashes",
                          "all highway approaches represented"],
        "termination_rules": ["900 contiguous Native frames at 20 Hz",
                              "failed source/camera/readback aborts capture"],
    }
    (directory / "construction.json").write_text(_json(construction))
    fallback = json.loads(_json(construction))
    fallback["candidate_id"] = "fallback1"
    fallback["files"] = [dict(entry) for entry in files]
    fallback_config = dict(config, spawn_offset_m=3.0)
    for entry in fallback["files"]:
        if entry["path"] == "config.json":
            entry["content"] = _json(fallback_config)
    (directory / "construction-fallback1.json").write_text(_json(fallback))
    return construction


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    constructions = [make(case) for case in plan["cases"]]
    (ROOT / "config.json").write_text(_json(json.loads(constructions[0]["files"][-2]["content"])))
    (ROOT / "construction.json").write_text(_json(constructions[0]))
    entries = []
    for case in plan["cases"]:
        variant = case["variant"]
        base = "cases/" + variant + "/"
        primary = ROOT / base / "construction.json"
        fallback = ROOT / base / "construction-fallback1.json"
        entries.append({
            "case_id": case["case_id"], "kind": "delivery",
            "construction": base + "construction.json",
            "construction_sha256": _sha(primary.read_bytes()),
            "candidate_risk": case["candidate_risk"],
            "candidates": [{"id": "fallback1",
                            "construction": base + "construction-fallback1.json",
                            "construction_sha256": _sha(fallback.read_bytes()),
                            "changed_knobs": ["spawn_offset_m: 0 to 3"],
                            "trigger": {"source": "original Native motion and collision feedback",
                                        "metric": "approach actor reaches connection",
                                        "failure_condition": "primary actor spawn obstructed before original connection"}}],
            "measurement_contract": "measurement-" + variant + ".json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
        })
    runtime_manifest = REPO / "runtime" / "SOURCE-MANIFEST.json"
    (ROOT / "execution-manifest.draft.json").write_text(_json({
        "format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": _sha(runtime_manifest.read_bytes()),
        "draft_missing_proofs": ["offline", "compatibility", "saved processing",
                                 "physical lifecycle", "independent delivery and comparison"],
        "cases": entries}))
    print(len(constructions))


if __name__ == "__main__":
    main()
