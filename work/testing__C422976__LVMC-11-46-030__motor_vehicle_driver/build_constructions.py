"""Build per-case inline source-gated Native construction candidates."""

import hashlib
import json
from pathlib import Path

from package_contract import ACTOR, CAMERAS, CELL, LAW, recording_description
from school_lane_controls import ASSIGNMENT


HERE = Path(__file__).resolve().parent
SOURCES = ("runner.py", "native_adapter.py", "reviewed_site.py", "school_lane_controls.py",
           "warning_actuation.py", "package_contract.py", "school_lane_observations.py",
           "analysis.py", "proposals/cases.json")
TEST = '''import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_site import plan

class ExactConstruction(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check_config(json.loads(Path("config.json").read_text())))

    def test_original_source_gate(self):
        case_id=json.loads(Path("config.json").read_text())["selected_case_id"]
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan(Path("."), {"path":"absent.json","sha256":"0"*64}, case_id)
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    cases = [c for c in proposal["cases"] if c.get("target_law_id") == LAW]
    if len(cases) != 15 or len({c["case_id"] for c in cases}) != 15:
        raise ValueError("exact 15-case selected set required")
    entries = []
    for index, case in enumerate(cases):
        case_id = case["case_id"]
        config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                  "selected_case_id": case_id, "diagnostic_only": True,
                  "supported_case_ids": [item["case_id"] for item in cases],
                  "rate_hz": 20, "duration_s": 45, "cameras": CAMERAS,
                  "required_atoms": [], "source_packets": [],
                  "physical_completion": {"required_frames": 900,
                                          "original_site_required": True,
                                          "reviewed_warning_and_release_required": True},
                  "stop_distance_target_ft": case["variable_assignments"]["stop_distance_target_ft"]["value"]}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")}
                 for name in SOURCES]
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
                      {"path": "tests/test_exact_construction.py", "content": TEST}])
        construction = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                        "case_id": case_id, "diagnostic_only": True,
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": recording_description(),
                        "mechanisms": ["reviewed original school lane and nearest-side geometry",
                                       "source-gated vehicle stop and human/device warning and release requests",
                                       "four synchronized original Native cameras"],
                        "measurement_plan": ["900 original 20 Hz body reference, actor-state and camera frames",
                                             "source-bound original annotation of human gesture and locality",
                                             "legal threshold convention remains unresolved"],
                        "static_checks": ["reviewed site, OpenDRIVE and actor source hashes",
                                          "exact selected variant or frozen judgment sampling station"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        relative = Path("construction.json") if index == 0 else Path("cases") / case_id.rsplit("__", 1)[-1] / "construction.json"
        write(HERE / relative, construction)
        plan = json.loads((HERE / "case-plan.json").read_text())
        requirements = []
        methods = ("school_lane_stop_observation", "school_lane_release_observation",
                   "school_lane_warning_observation")
        for disposition_index, method in enumerate(methods):
            requirement = plan["requirement_dispositions"][disposition_index]
            requirements.append({"disposition_index": disposition_index,
                                 "requirement": requirement["requirement"],
                                 "source": requirement["source"],
                                 "output_key": method, "method": method,
                                 "value_type": "object", "kind": "measured",
                                 "inputs": ["context.json", "trace.json"]})
        contract_path = HERE / ("measurement-contract.json" if index == 0 else
                               "cases/" + case_id.rsplit("__", 1)[-1] + "/measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract",
                              "requirements": requirements,
                              "negative": {"remove": ["context.json"],
                                           "error_contains": "Missing required source: context.json"}})
        entries.append({"case_id": case_id, "kind": "diagnostic", "construction": str(relative),
                        "construction_sha256": hashlib.sha256((HERE / relative).read_bytes()).hexdigest(),
                        "measurement_contract": "measurement-contract.json" if index == 0 else
                            "cases/" + case_id.rsplit("__", 1)[-1] + "/measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/cases/" +
                            case_id.rsplit("__", 1)[-1] + "/diagnostic-recipe.json",
                        "candidate_risk": {"status": "none", "reason": "Original reviewed school-lane site and actor assets require local physical review before fallback selection."},
                        "candidates": []})
        if index == 0:
            write(HERE / "config.json", config)
    repo = HERE.parents[1]
    write(HERE / "diagnostic-execution-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
           "runtime_manifest_sha256": hashlib.sha256((repo / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
           "diagnostic_only": True, "cases": entries})
    print("Built 15 exact source-gated constructions")


if __name__ == "__main__":
    main()
