"""Build five exact pedestrian diagnostic constructions and contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from curb_entry import CASES
from delivery_audit import ASSIGNMENT


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SOURCE_FILES = ("runner.py", "curb_entry.py", "reviewed_scene.py",
                "native_adapter.py", "delivery_audit.py", "comparison_audit.py",
                "process_recorded_only.py", "analysis.py")
CAMERAS = ["overview", "approach", "reference_corner", "driver_reference"]
TEST = '''import json
import unittest
from runner import check_config


class ConstructionTest(unittest.TestCase):
    def test_contract(self):
        with open("config.json", encoding="utf-8") as stream:
            self.assertTrue(check_config(json.load(stream)))

    def test_original_source_gate(self):
        from pathlib import Path
        from reviewed_scene import plan
        case_id = json.load(open("config.json", encoding="utf-8"))["selected_case_id"]
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan(Path("."), {"path": "absent.json", "sha256": "0" * 64}, case_id)
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def recording_description() -> dict:
    names = (
        ("pedestrian and curb geometry", "original pedestrian position and reviewed curb geometry"),
        ("pedestrian and vehicle trajectories", "20 Hz original synchronized actor positions and speeds"),
        ("vehicle path and driver", "original driver-controlled vehicle and path readback"),
        ("four synchronized camera views", "20 Hz original Native RGB cameras"),
    )
    channels = [{"name": name, "unit": "source observation", "method": method,
                 "reference_frame": "same original Native frame and simulation time",
                 "sampling_rate_hz": 20, "time_window": "45-second original episode",
                 "uncertainty": "Suddenness, impossibility to yield and exceptions require independent review"}
                for name, method in names]
    context = [{"name": "reviewed curb, roadway and driver authority",
                "unit": "source record", "method": "SHA-256-sealed original site and actor readback"}]
    return {"channels": channels, "context_inputs": context,
            "limitations": ["Proximity is an observation, not a legal impossibility threshold.",
                            "Walking or running does not alone establish suddenness.",
                            "Introductory exceptions remain unresolved."]}


def main():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    description = recording_description()
    entries = []
    for index, case in enumerate(CASES):
        case_id = ASSIGNMENT + "__" + case.name
        config = {"law_id": "NRS-484B-283-1b", "cell_id": "C228096",
                  "actor": "pedestrian", "selected_case_id": case_id,
                  "supported_case_ids": [ASSIGNMENT + "__" + item.name for item in CASES],
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": CAMERAS, "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id, "variant": case.name},
                  "physical_completion": {"required_frames": 900,
                                          "original_site_required": True,
                                          "reviewed_curb_and_vehicle_path_required": True}}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")}
                 for name in SOURCE_FILES]
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_diagnostic_bundle.py", "content": TEST}])
        construction = {"law_id": "NRS-484B-283-1b", "cell_id": "C228096",
                        "actor": "pedestrian", "case_id": case_id,
                        "diagnostic_only": True, "entrypoint": "runner.py",
                        "files": files, "recording_description": description,
                        "mechanisms": ["reviewed original curb and OpenDRIVE roadway",
                                       "source-isolated pedestrian path, gait and vehicle start",
                                       "four synchronized Native cameras"],
                        "measurement_plan": ["900 original 20 Hz actor trajectory frames",
                                             "separate roadway and vehicle-path entry",
                                             "four-camera original video and full decode"],
                        "static_checks": ["reviewed site and OpenDRIVE source hashes",
                                          "five exact route/gait/gap variants"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        construction_rel = "construction.json" if index == 0 else \
            "cases/" + case.name + "/construction.json"
        write(HERE / construction_rel, construction)
        contract = {"format": "worker-measurement-contract",
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["law_text"],
                                      "source": plan["witness_review"][0]["source"],
                                      "output_key": "pedestrian_path_entry_observation",
                                      "method": "pedestrian_path_entry_observation",
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["site.json", "trace.json"]}],
                    "negative": {"remove": ["trace.json"],
                                 "error_contains": "Missing required source: trace.json"}}
        contract_rel = "measurement-contract.json" if index == 0 else \
            "cases/" + case.name + "/measurement-contract.json"
        write(HERE / contract_rel, contract)
        entries.append({"case_id": case_id, "kind": "diagnostic",
                        "construction": construction_rel,
                        "construction_sha256": sha(HERE / construction_rel),
                        "measurement_contract": contract_rel,
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/cases/" + case.name +
                                          "/diagnostic-recipe.json",
                        "candidate_risk": {"status": "none", "reason":
                            "No source-reviewed alternate curb, driver path or timing is available; evaluate original attempt before adding an engineering fallback."},
                        "candidates": []})
    write(HERE / "diagnostic-execution-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
           "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
           "diagnostic_only": True, "cases": entries})
    print("Built five exact source-gated diagnostic constructions")


if __name__ == "__main__":
    main()
