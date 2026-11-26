"""Rebuild four source-gated diagnostic Native bundles from package-local code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FILES = ("runner.py", "native_adapter.py", "analysis.py", "cycle_lane_native.py",
         "cycle_lane_original.py", "cycle_lane_site.py", "cycle_lane_intersection.py",
         "case-plan.json")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    existing_path = ROOT / "diagnostic-execution-manifest.json"
    existing = json.loads(existing_path.read_text()) if existing_path.is_file() else {}
    previous = {entry["case_id"]: entry for entry in existing.get("cases", [])}
    ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(plan["assignment_id"] + "__")
        config = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "selected_case_id": case_id,
                  "supported_case_ids": ids, "rate_hz": 20, "duration_s": 45,
                  "cameras": list(VIEWS), "diagnostic_only": True,
                  "route_candidate_id": suffix,
                  "requested_overlap": case["requested_cycle_lane_intersection_overlap"],
                  "requested_subsection_3_status": case["requested_subsection_3_exception_status"],
                  "required_atoms": [], "source_packets": []}
        check = ("import json\nimport unittest\nfrom pathlib import Path\n"
                 "from runner import check_config\n"
                 "from cycle_lane_native import prepare\n"
                 "class BundleTest(unittest.TestCase):\n"
                 "    def test_exact_case_config(self):\n"
                 "        self.assertTrue(check_config(json.loads(Path('config.json').read_text())))\n"
                 "    def test_reviewed_source_required(self):\n"
                 "        config=json.loads(Path('config.json').read_text())\n"
                 "        with self.assertRaises(ValueError):\n"
                 "            prepare(config['selected_case_id'], Path('missing-site.json'), '0'*64,\n"
                 "                    Path('missing-exception.json'), '0'*64,\n"
                 "                    Path('missing-vehicle.json'), '0'*64, config['route_candidate_id'])\n")
        files = [{"path": name, "content": (ROOT / name).read_text(encoding="utf-8")}
                 for name in FILES]
        files.extend(({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_bundle.py", "content": check}))
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                        "actor": plan["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "files": files,
                        "recording_description": {"channels": [
                            {"name": "ego_body_polygon", "unit": "Native world XY",
                             "sampling_rate_hz": 20, "method": "Original Native bbox hull",
                             "time_window": "45-second full capture",
                             "reference_frame": "original Native world",
                             "uncertainty": "physical capture requires review"},
                            {"name": "intersection_cycle_lane_overlap", "unit": "boolean",
                             "sampling_rate_hz": 20,
                             "method": "Original body polygon and reviewed site polygons",
                             "time_window": "45-second full capture",
                             "reference_frame": "original Native world",
                             "uncertainty": "subsection 3 is independent"}],
                            "context_inputs": [{"name": "reviewed_site_and_subsection_3",
                                                "unit": "source packet",
                                                "method": "Independent SHA-256 review"}],
                            "limitations": ["Diagnostic CPU fixture is not original evidence.",
                                            "Native physical capture and source review pending."]},
                        "mechanisms": ["reviewed OpenDRIVE public intersection",
                                       "reviewed designated cycle-lane polygon and route",
                                       "source-reviewed motor vehicle/driver",
                                       "four synchronized Native RGB views"],
                        "measurement_plan": ["900 original 20 Hz frame/body polygon joins",
                                             "independent subsection 3 source review",
                                             "full four-camera decode"],
                        "termination_rules": {"frames": 900, "native_sync_required": True}}
        location = ROOT / "cases" / suffix / "construction.json"
        digest = write(location, construction)
        entries.append({"case_id": case_id, "construction": str(location.relative_to(ROOT)),
                        "construction_sha256": digest,
                        "measurement_contract": "measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": str((ROOT / "cases" / suffix / "diagnostic-recipe.json").relative_to(ROOT.parents[1])),
                        "candidate_risk": {
                            "status": "none", "reason": "Physical route/lane behavior requires source map and Native review before selecting an alternate."},
                        "candidates": [], "kind": "diagnostic_unselected"})
        old = previous.get(case_id, {})
        proof = old.get("offline", {})
        log = ROOT / proof.get("log", "")
        if (proof.get("construction_sha256") == digest and log.is_file() and
                hashlib.sha256(log.read_bytes()).hexdigest() == proof.get("log_sha256")):
            entries[-1]["offline"] = proof
    manifest = {"assignment_id": plan["assignment_id"],
                "runtime_manifest_sha256": hashlib.sha256(
                    (ROOT.parents[1] / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                "cases": entries, "comparisons": plan["comparisons"],
                "status": "diagnostic_offline_only", "physical_acceptance_claimed": False}
    write(ROOT / "diagnostic-execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"cases": len(result["cases"]), "status": result["status"]}))
