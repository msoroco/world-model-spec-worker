"""Build six exact engineering diagnostic bundles from pinned sweep expansion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reviewed_scene import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
MAP = {
    "runner.py": "engineering_bundle_runner.py",
    "analysis.py": "engineering_analysis.py",
    "base_analysis.py": "base_analysis.py",
    "engineering_sweep_station.py": "engineering_sweep_station.py",
    "build_engineering_sweep_preview.py": "build_engineering_sweep_preview.py",
    "engineering_sweep_runner.py": "engineering_sweep_runner.py",
    "sweep_native_adapter.py": "sweep_native_adapter.py",
    "reviewed_scene.py": "reviewed_scene.py",
    "native_adapter.py": "native_adapter.py",
    "right_lane_measurement.py": "right_lane_measurement.py",
    "finalize_follower.py": "finalize_follower.py",
    "delivery_audit.py": "delivery_audit.py",
    "comparison_audit.py": "comparison_audit.py",
    "process_recorded_only.py": "process_recorded_only.py",
}
TEST = '''import json
import unittest
from runner import check_config

class ConstructionTest(unittest.TestCase):
    def test_selected_contract(self):
        with open("config.json", encoding="utf-8") as stream:
            self.assertTrue(check_config(json.load(stream)))

    def test_original_source_gate(self):
        from engineering_sweep_station import plan_engineering
        from pathlib import Path
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan_engineering(Path("."), {"path": "absent.json", "sha256": "0" * 64},
                             json.load(open("config.json", encoding="utf-8"))["selected_case_id"])
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(expanded: Path) -> dict:
    proposal = json.loads(Path(expanded).read_text(encoding="utf-8"))
    selected = [case for case in proposal["cases"] if case.get("target_type") == "judgment_sweep"]
    if len(selected) != 6 or len({case["case_id"] for case in selected}) != 6:
        raise ValueError("pinned expansion must contain six exact engineering cases")
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    entries = []
    for case in selected:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        if suffix not in {f"{axis}-{rank:04d}" for axis in ("impediment", "passing_necessity")
                          for rank in range(3)}:
            raise ValueError("unassigned engineering case")
        config = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "selected_case_id": case_id,
                  "supported_case_ids": [row["case_id"] for row in selected],
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id, "variant": suffix,
                           "engineering_setpoint": case["sweep_point"]},
                  "physical_completion": {"required_frames": 900,
                                          "original_site_required": True,
                                          "reviewed_lane_markings_required": True}}
        files = [{"path": target, "content": (ROOT / source).read_text(encoding="utf-8")}
                 for target, source in MAP.items()]
        files.extend([{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_engineering_bundle.py", "content": TEST}])
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"], "actor": plan["actor"],
            "case_id": case_id, "diagnostic_only": True, "entrypoint": "runner.py",
            "files": files, "recording_description": case["recording_description"],
            "mechanisms": ["reviewed OpenDRIVE route and marked lane source gate",
                           "one bounded authored speed request and measured actor readback",
                           "four synchronized Native cameras"],
            "measurement_plan": ["900 original 20 Hz actor speed/lane/follower frames",
                                 "independent immediate-follower relation and four-camera decode",
                                 "original speed readback separately from request"],
            "static_checks": ["reviewed site and map hashes", "right/middle marked lane order",
                              "exact bounded engineering station"],
            "termination_rules": {"frames": 900, "native_sync_required": True}}
        folder = ROOT / "cases" / suffix
        write(folder / "construction.json", construction)
        contract = {"format": "worker-measurement-contract", "requirements": [{
            "disposition_index": 0, "requirement": plan["law_text"],
            "source": plan["witness_review"][0]["source"],
            "output_key": "right_lane_follower_observation",
            "method": "right_lane_follower_observation", "value_type": "object",
            "kind": "measured", "inputs": ["trace.json", "relation.json"]}],
            "negative": {"remove": ["relation.json"],
                         "error_contains": "Missing required source: relation.json"}}
        write(folder / "measurement-contract.json", contract)
        entries.append({"case_id": case_id, "kind": "diagnostic",
                        "construction": f"cases/{suffix}/construction.json",
                        "construction_sha256": sha(folder / "construction.json"),
                        "measurement_contract": f"cases/{suffix}/measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": str((folder / "diagnostic-recipe.json").relative_to(REPO)),
                        "candidate_risk": {"status": "none", "reason":
                          "Actual sampled speed, lane and follower relation need original motion review; no source-reviewed alternative station has been supplied."},
                        "candidates": []})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "diagnostic_only": True, "cases": entries}
    write(ROOT / "engineering-diagnostic-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"cases": len(build(args.expanded)["cases"])}))
