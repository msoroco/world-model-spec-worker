"""Build six exact source-gated red-plus-arrow Native constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCES = ("runner.py", "native_turn.py", "native_capture.py",
           "saved_turn.py", "saved_pair.py", "comparison_audit.py",
           "delivery_audit.py", "analysis.py")
VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class ExactBundleTests(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        case = runner.check()
        self.assertEqual(case["selected_case_id"], json.loads(Path("config.json").read_text())["selected_case_id"])
        with self.assertRaisesRegex(ValueError, "reviewed original C111610 red-arrow site packet missing"):
            runner.run_native(Path.cwd(), Path("unused-output"), Path.cwd())


if __name__ == "__main__":
    unittest.main()
'''


def build():
    plan_raw = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_raw)
    if (plan["assignment_id"] != ASSIGNMENT or len(plan["cases"]) != 6 or
            len(plan["comparisons"]) != 4):
        raise ValueError("fixed red-plus-arrow case coverage changed")
    case_ids = [item["case_id"] for item in plan["cases"]]
    channels = [{"name": item["name"], "unit": "structured record",
                 "sampling_rate_hz": 20,
                 "method": item["description"],
                 "time_window": "approach through intersection clearance",
                 "reference_frame": "original Native frame and time",
                 "uncertainty": "20 Hz sampling and original sensor/source precision"}
                for item in plan["observations"]]
    recording = {
        "channels": channels,
        "context_inputs": [{"name": "reviewed_original_site", "unit": "structured record",
                            "method": "Hash-sealed map, heads, crosswalk and actor permission sources."}],
        "limitations": ["Physical signal, actor and camera realization requires original Native review.",
                        "Lawful use and right of way remain source-dependent judgments."],
    }
    cases = []
    for item in plan["cases"]:
        suffix = item["case_suffix"]
        case_id = ASSIGNMENT + "__" + suffix
        if item["case_id"] != case_id:
            raise ValueError("exact red-plus-arrow case identity changed")
        cameras = [{"name": name, "width": width, "height": height,
                    "pose_strategy": "source-reviewed intersection coverage",
                    "fov_deg": 90} for name, width, height in VIEWS]
        config = {"assignment_id": ASSIGNMENT, "law_id": plan["law_id"],
                  "cell_id": plan["cell_id"], "actor": plan["actor"],
                  "selected_case_id": case_id, "case_suffix": suffix,
                  "supported_case_ids": case_ids,
                  "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
                  "rate_hz": 20, "fps": 20, "frame_count": 600,
                  "duration_s": 30, "cameras": cameras,
                  "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id,
                           "recording_description": recording},
                  "physical_completion": {"criterion": "turn" if suffix != "wrong_movement" else "travel_progress",
                                          "motion_source": "body_history.jsonl",
                                          "body_key": "body_vertices_m",
                                          "heading_key": "heading_deg",
                                          "turn_degrees": 90,
                                          "turn_tolerance_deg": 30,
                                          "minimum_progress_m": 1.0,
                                          "context_sources": []}}
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({"case-plan.json": plan_raw.decode(),
                      "camera_profile.json": (HERE / "camera_profile.json").read_text(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": False,
            "recording_description": recording,
            "measurement_plan": [{"requirement": row["requirement"],
                                  "source": row["source"]}
                                 for row in plan["requirement_dispositions"]],
            "static_checks": ["exact plan hash", "reviewed site source hashes",
                              "canonical camera profile", "source-bound actor spawns"],
            "termination_rules": ["600 original ticks at 20 Hz",
                                  "restore world settings and destroy owned actors"],
            "mechanisms": ["reviewed official signal observation",
                           "source-gated Native movement and original camera capture"],
            "files": [{"path": path, "content": content}
                      for path, content in files.items()],
        }
        path = HERE / ("construction.json" if suffix == "yield_pedestrian"
                       else "construction-" + suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        case_dir = HERE / "cases" / suffix
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "config.json").write_text(files["config.json"])
        (case_dir / "construction.json").write_text(path.read_text())
        output_keys = ("signal_and_movement", "pedestrian_precedence",
                       "other_traffic_precedence", "opposing_red_advisory",
                       "exception_actor_scope")
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": row["disposition_index"],
                                      "requirement": row["requirement"],
                                      "source": row["source"],
                                      "output_key": output_keys[index],
                                      "method": "measure_case", "value_type": "object",
                                      "kind": "measured" if index < 4 else "sourced_context",
                                      "inputs": ["red-arrow-observations.json", "source_site.json"]}
                                     for index, row in enumerate(plan["requirement_dispositions"])],
                    "negative": {"remove": ["red-arrow-observations.json"],
                                 "error_contains": "Missing required source: red-arrow-observations.json"}}
        contract_path = case_dir / "measurement-contract.json"
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        cases.append({"case_id": case_id, "construction": path.name,
                      "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "kind": "delivery",
                      "acquisition": {name: {"entrypoint": "analysis.py",
                                             "method": "Source-verified original Native red-arrow replay, with explicit synthetic diagnostic branch",
                                             "evidence": "channels/" + name + ".jsonl"}
                                      for name in (o["name"] for o in plan["observations"])},
                      "measurement_procedure": {"entrypoint": "analysis.py"},
                      "measurement_contract": str(contract_path.relative_to(HERE)),
                      "fixture_recipe": str((HERE / ("diagnostic-" + suffix + "-recipe.json")).relative_to(HERE.parent.parent)),
                      "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                         "host_env_var": "CARLA_HOST",
                                         "port_env_var": "CARLA_PORT"},
                      "candidate_risk": {"status": "none",
                                         "reason": "The documented failure modes are unavailable or mismatched original signal/permission sources, missing actor readbacks, and failed original camera or motion evidence. A different control or route knob cannot establish those source facts; the strict Native and saved audits reject such attempts."},
                      "candidates": []})
        if suffix == "yield_pedestrian":
            (HERE / "config.json").write_text(files["config.json"])
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": ASSIGNMENT,
        "status": "exact_offline_constructions_only",
        "cases": cases}, indent=2) + "\n")
    # Keep the exact identities and construction hashes in the selected manifest.
    # Subsequent proof authoring adds the case-specific finalizer, diagnostic
    # receipts, and independent delivery/comparison audit bindings.
    runtime_manifest = HERE.parent.parent / "runtime" / "SOURCE-MANIFEST.json"
    (HERE / "execution-manifest.json").write_text(json.dumps({
        "format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": hashlib.sha256(runtime_manifest.read_bytes()).hexdigest(),
        "cases": cases,
    }, indent=2) + "\n")
    print("built", len(cases), "source-gated Native constructions")


if __name__ == "__main__":
    build()
