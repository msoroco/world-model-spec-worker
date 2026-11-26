"""Build all exact inline Native constructions and selected measurement contracts."""

import hashlib
import json
from pathlib import Path

from package_contract import ACTOR, ASSIGNMENT, CAMERAS, CELL, LAW
from hov_controls import selected_schedule

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCES = ("runner.py", "native_adapter.py", "reviewed_site.py", "hov_controls.py",
           "package_contract.py", "hov_encounter_observations.py", "analysis.py",
           "proposals/cases.json")
METHODS = ("controlled_access_lane_observation", "posted_limit_knowledge_observation",
           "faster_rear_overtaking_observation", "continued_left_lane_observation",
           "hov_qualification_observation", "other_exception_observation")
TEST = '''import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_site import plan

class ExactConstruction(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check_config(json.loads(Path("config.json").read_text())))

    def test_original_authority_gate(self):
        case_id=json.loads(Path("config.json").read_text())["selected_case_id"]
        with self.assertRaises(ValueError):
            plan(Path("."), {"path":"absent.json","sha256":"0"*64}, case_id)
'''


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = [c for c in proposal["cases"] if c.get("target_law_id") == LAW]
    if len(cases) != 18 or {c["case_id"] for c in cases} != {c["case_id"] for c in plan["cases"]}:
        raise ValueError("exact eighteen selected cases required")
    description = cases[0]["recording_description"]
    entries = []
    for index, case in enumerate(cases):
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                  "selected_case_id": case_id, "diagnostic_only": True,
                  "supported_case_ids": [c["case_id"] for c in cases],
                  "rate_hz": 20, "duration_s": 45, "cameras": CAMERAS,
                  "required_atoms": [], "source_packets": [],
                  "physical_completion": {"required_frames": 900,
                                          "reviewed_original_highway_required": True,
                                          "original_hov_authority_and_actor_readback_required": True},
                  "ego_target_speed_mps": selected_schedule(case_id, 8.0)["ego_target_speed_mps"],
                  "controller_requests": case.get("variable_assignments", {})}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")}
                 for name in SOURCES]
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
                      {"path": "tests/test_exact_construction.py", "content": TEST}])
        construction = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                        "case_id": case_id, "diagnostic_only": True,
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": description,
                        "mechanisms": ["reviewed original controlled-access two-lane/HOV authority",
                                       "source-gated ego/rear speed and right-lane response controls",
                                       "source-gated sign onset and reviewed original occupancy request",
                                       "four synchronized original Native RGB cameras"],
                        "measurement_plan": ["900 original 20 Hz ego/rear actor, lane, speed and gap samples",
                                             "original HOV designation, hours, signs, access, occupancy and category packets",
                                             "knowledge, persistence, overtaking and HOV legal judgments unresolved"],
                        "static_checks": ["exact selected case identity and reviewed source SHA-256",
                                          "marked same-direction lanes and extreme-left actor spawn",
                                          "four-camera and actuator readback capabilities"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        relative = Path("construction.json") if index == 0 else Path("cases") / suffix / "construction.json"
        write(HERE / relative, construction)
        requirements = []
        for i, method in enumerate(METHODS):
            disposition = plan["requirement_dispositions"][i]
            requirements.append({"disposition_index": i, "requirement": disposition["requirement"],
                                 "source": disposition["source"], "output_key": method,
                                 "method": method, "value_type": "object", "kind": "measured",
                                 "inputs": ["context.json", "trace.json"]})
        contract_relative = Path("measurement-contract.json") if index == 0 else Path("cases") / suffix / "measurement-contract.json"
        write(HERE / contract_relative, {"format": "worker-measurement-contract",
                                         "requirements": requirements,
                                         "negative": {"remove": ["context.json"],
                                                      "error_contains": "Missing required source: context.json"}})
        entries.append({"case_id": case_id, "kind": "diagnostic",
                        "construction": str(relative),
                        "construction_sha256": hashlib.sha256((HERE / relative).read_bytes()).hexdigest(),
                        "measurement_contract": str(contract_relative),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/cases/" + suffix + "/diagnostic-recipe.json",
                        "candidate_risk": {"status": "none", "reason": "No alternative source-reviewed highway site or HOV authority is available for a justified fallback."},
                        "candidates": []})
        if index == 0:
            write(HERE / "config.json", config)
            test_path = HERE / "tests/test_exact_construction.py"
            test_path.write_text(TEST, encoding="utf-8")
    write(HERE / "diagnostic-execution-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
           "runtime_manifest_sha256": hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
           "diagnostic_only": True, "cases": entries})
    print("Built 18 exact source-gated Native constructions and measurement contracts")


if __name__ == "__main__":
    main()
