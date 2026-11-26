"""Build four exact pedestrian signal diagnostic constructions and contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ped_entry import CASES
from delivery_audit import ASSIGNMENT

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SOURCE_FILES = ("runner.py", "ped_entry.py", "reviewed_scene.py",
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
        ("pedestrian and highway boundary", "original pedestrian body distance to reviewed highway boundary"),
        ("official red and green turn arrow", "20 Hz original concurrent signal actor readback"),
        ("other device display and facing", "20 Hz other-device and pedestrian-facing readback"),
        ("four synchronized camera views", "20 Hz original Native RGB cameras"),
    )
    channels = [{"name": name, "unit": "source observation", "method": method,
                 "reference_frame": "same original Native frame and simulation time",
                 "sampling_rate_hz": 20, "time_window": "45-second original episode",
                 "uncertainty": "NRS 484B.283 other-device permission and actual signal appearance require independent review"}
                for name, method in names]
    context = [{"name": "reviewed highway, signal and device authority",
                "unit": "source record", "method": "SHA-256-sealed original site, map and signal assets"}]
    return {"channels": channels, "context_inputs": context,
            "limitations": ["A green vehicle arrow is not pedestrian permission.",
                            "Another device's WALK display does not alone resolve NRS 484B.283 permission.",
                            "Actual highway dedication, public use, facing and signal assets require independent review."]}


def main():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    description = recording_description()
    entries = []
    for index, case in enumerate(CASES):
        case_id = ASSIGNMENT + "__" + case.case_id
        config = {"law_id": "NRS-484B-307-9c", "cell_id": "C227824",
                  "actor": "pedestrian", "selected_case_id": case_id,
                  "supported_case_ids": [ASSIGNMENT + "__" + item.case_id for item in CASES],
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": CAMERAS, "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id, "variant": case.case_id},
                  "physical_completion": {"required_frames": 900,
                                          "original_site_required": True,
                                          "reviewed_signal_and_highway_required": True}}
        files = [{"path": name, "content": (HERE / name).read_text(encoding="utf-8")}
                 for name in SOURCE_FILES]
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_diagnostic_bundle.py", "content": TEST}])
        construction = {"law_id": "NRS-484B-307-9c", "cell_id": "C227824",
                        "actor": "pedestrian", "case_id": case_id,
                        "diagnostic_only": True, "entrypoint": "runner.py",
                        "files": files, "recording_description": description,
                        "mechanisms": ["reviewed original highway/OpenDRIVE and red/arrow/device assets",
                                       "source-isolated pedestrian entry versus wait and other-device display",
                                       "four synchronized Native cameras"],
                        "measurement_plan": ["900 original 20 Hz body-to-boundary and signal frames",
                                             "first actual highway entry from outside",
                                             "four-camera original video and full decode"],
                        "static_checks": ["reviewed site, map and signal asset source hashes",
                                          "four exact entry/wait and device variants"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        construction_rel = "construction.json" if index == 0 else \
            "cases/" + case.case_id + "/construction.json"
        write(HERE / construction_rel, construction)
        contract = {"format": "worker-measurement-contract",
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["law_text"],
                                      "source": plan["witness_review"][0]["source"],
                                      "output_key": "pedestrian_signal_entry_observation",
                                      "method": "pedestrian_signal_entry_observation",
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["site.json", "trace.json"]}],
                    "negative": {"remove": ["trace.json"],
                                 "error_contains": "Missing required source: trace.json"}}
        contract_rel = "measurement-contract.json" if index == 0 else \
            "cases/" + case.case_id + "/measurement-contract.json"
        write(HERE / contract_rel, contract)
        entries.append({"case_id": case_id, "kind": "diagnostic",
                        "construction": construction_rel,
                        "construction_sha256": sha(HERE / construction_rel),
                        "measurement_contract": contract_rel,
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/cases/" + case.case_id +
                                          "/diagnostic-recipe.json",
                        "candidate_risk": {"status": "none", "reason":
                            "No source-reviewed alternate signal asset or highway station is available; evaluate first original attempt before selecting a fallback."},
                        "candidates": []})
    write(HERE / "diagnostic-execution-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
           "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
           "diagnostic_only": True, "cases": entries})
    print("Built four exact source-gated signal diagnostic constructions")


if __name__ == "__main__":
    main()
