"""Build source-gated diagnostic bundles for all four exact case IDs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS

HERE = Path(__file__).resolve().parent
LAW = "NRS-484B-627-1b"
CELL = "C147344"
ACTOR = "motor_vehicle_driver"
SRC = ("runner.py", "reviewed_scene.py", "native_adapter.py",
       "right_lane_measurement.py", "finalize_follower.py", "delivery_audit.py",
       "comparison_audit.py", "process_recorded_only.py", "analysis.py")
TEST = '''import json
import unittest
from runner import check_config


class ConstructionTest(unittest.TestCase):
    def test_contract(self):
        with open("config.json", encoding="utf-8") as stream:
            self.assertTrue(check_config(json.load(stream)))

    def test_source_gate(self):
        from reviewed_scene import plan
        from pathlib import Path
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan(Path("."), {"path": "absent.json", "sha256": "0" * 64},
                 json.load(open("config.json", encoding="utf-8"))["selected_case_id"])
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    semantic = json.loads((HERE / "proposals/cases.json").read_text(encoding="utf-8"))
    descriptions = {row["case_id"]: row["recording_description"] for row in semantic["cases"]}
    entries = []
    for index, suffix in enumerate(VARIANTS):
        case_id = ASSIGNMENT + "__" + suffix
        config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                  "selected_case_id": case_id, "supported_case_ids": [ASSIGNMENT + "__" + s for s in VARIANTS],
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "required_atoms": [],
                  "source_packets": [],
                  "case": {"case_id": case_id, "variant": suffix},
                  "physical_completion": {"required_frames": 900, "original_site_required": True,
                                          "reviewed_lane_markings_required": True}}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")} for name in SRC]
        files += [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                  {"path": "tests/test_diagnostic_bundle.py", "content": TEST}]
        construction = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR, "case_id": case_id,
                        "diagnostic_only": True, "entrypoint": "runner.py", "files": files,
                        "recording_description": descriptions[case_id],
                        "mechanisms": ["source-reviewed OpenDRIVE lane/station scene", "three vehicles or same-lane follower according to exact variant", "four synchronized cameras"],
                        "measurement_plan": ["900 original 20 Hz actor/lane/follower frames", "independent immediate-follower relation", "four-camera original video and full decode"],
                        "static_checks": ["reviewed site hash and original map hash", "two clearly marked same-direction lanes", "variant actor/lane ordering"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        rel = "construction.json" if index == 0 else f"cases/{suffix}/construction.json"
        write(HERE / rel, construction)
        plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
        contract = {"format": "worker-measurement-contract",
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["law_text"],
                                      "source": plan["witness_review"][0]["source"],
                                      "output_key": "right_lane_follower_observation",
                                      "method": "right_lane_follower_observation",
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["trace.json", "relation.json"]}],
                    "negative": {"remove": ["relation.json"],
                                 "error_contains": "Missing required source: relation.json"}}
        crel = "measurement-contract.json" if index == 0 else f"cases/{suffix}/measurement-contract.json"
        write(HERE / crel, contract)
        entries.append({"case_id": case_id, "kind": "diagnostic", "construction": rel,
                        "construction_sha256": digest(HERE / rel), "measurement_contract": crel,
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": str((HERE / f"cases/{suffix}/diagnostic-recipe.json").relative_to(HERE.parent.parent)),
                        "candidate_risk": {"status": "none", "reason": "Physical follower gap and lane retention risk requires original observation; no source-reviewed alternate spawn geometry is available."},
                        "candidates": []})
    runtime_sha = digest(HERE.parent.parent / "runtime/SOURCE-MANIFEST.json")
    write(HERE / "diagnostic-execution-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
           "runtime_manifest_sha256": runtime_sha, "diagnostic_only": True, "cases": entries})


if __name__ == "__main__":
    main()
