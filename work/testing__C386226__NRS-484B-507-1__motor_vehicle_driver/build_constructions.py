"""Regenerate twelve exact original-source-gated Native construction bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from freight_zone import CASES

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    base = json.loads((HERE / "config.json").read_text())
    cases = []
    for case in CASES:
        exact = AID + "__" + case.name
        config = dict(base)
        config["selected_case_id"] = exact
        config["case"] = {
            "case_id": exact, "name": case.name, "conduct": case.conduct,
            "material_action": case.material_action, "activity_delay_s": case.activity_delay_s,
            "hours": case.hours, "passenger_action": case.passenger_action,
            "freight_arrival": case.freight_arrival,
            "recording_description": base["case"]["recording_description"],
        }
        scene = {"case_id": exact, "source_status": "reviewed_original_site_required_at_capture",
                 "accepted_original_source": False, "source_kind": "source_deferred_original"}
        test = ("\"\"\"Exact source-gated Native bundle check.\"\"\"\n"
                "import unittest\nfrom runner import check\n\n"
                "class BundleTest(unittest.TestCase):\n"
                "    def test_exact_bundle(self):\n"
                "        case_id, case = check()\n"
                "        self.assertEqual(case_id, '" + exact + "')\n"
                "        self.assertEqual(case.name, '" + case.name + "')\n")
        files = [
            {"path": "runner.py", "content": (HERE / "runner.py").read_text()},
            {"path": "original_runner.py", "content": (HERE / "original_runner.py").read_text()},
            {"path": "freight_zone.py", "content": (HERE / "freight_zone.py").read_text()},
            {"path": "config.json", "content": json.dumps(config, indent=2, ensure_ascii=False) + "\n"},
            {"path": "scene.json", "content": json.dumps(scene, indent=2, ensure_ascii=False) + "\n"},
            {"path": "tests/test_bundle.py", "content": test},
        ]
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                        "actor": plan["actor"], "case_id": exact, "entrypoint": "runner.py",
                        "recording_description": config["case"]["recording_description"],
                        "measurement_plan": {"case_id": exact, "procedure": "finalize_saved.py",
                                             "original_frames": 900, "legal_judgment": "unresolved",
                                             "source_packets": ["reviewed_original_freight_site",
                                                                "original_native_capture", "four_camera_pixels",
                                                                "civil_clock_and_applicable_provision",
                                                                "materials_passenger_and_freight_activity"]},
                        "mechanisms": ["source-gated freight-curb construction",
                                       "same-tick PipelineCapture and four original cameras",
                                       "900-frame material, passenger and freight entry chronology"],
                        "static_checks": ["exact law/cell/case identity", "reviewed source provenance and site hash",
                                          "four-camera 20 Hz original frame joins"],
                        "termination_rules": ["900 original ticks at 20 Hz",
                                              "fail closed on missing original site or Native observation"],
                        "files": files}
        path = HERE / ("construction.json" if case == CASES[0] else "construction-" + case.name + ".json")
        write(path, construction)
        cases.append({"case_id": exact, "kind": "delivery",
                      "construction": path.name, "construction_sha256": sha(path),
                      "source_gate": "Original marked freight zone, applicable provision, civil clock, actual material/passenger activity and freight entry require local source review.",
                      "measurement_procedure": {"entrypoint": "finalize_saved.py"},
                      "candidate_risk": {"status": "physical", "reason": "Curb zone, material transfer and a waiting freight vehicle may not remain visible together; original geometry and sight lines need review."},
                      "candidates": []})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "source_gated_cpu_construction_partial", "cases": cases}
    write(HERE / "execution-manifest.json", manifest)
    # The root bundle is also the materialization source for exact case one.
    (HERE / "scene.json").write_text(next(f["content"] for f in json.loads((HERE / "construction.json").read_text())["files"] if f["path"] == "scene.json"))


if __name__ == "__main__":
    build()
