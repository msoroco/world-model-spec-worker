"""Build five exact door-action diagnostic bundles for pinned offline proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
KINDS = ("open_near_overlap", "open_near_clear", "open_far_side", "board_near", "alight_near")

RUNNER = '''"""Exact door-action diagnostic entrypoint."""
import argparse
import hashlib
import json
from pathlib import Path
from site_contract import CASE_ACTIONS
from native_capture import CAMERAS, RATE_HZ, FRAME_COUNT


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("case plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    if case not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected case absent from exact plan")
    kind = case.removeprefix(config["assignment_id"] + "__")
    if kind not in CASE_ACTIONS or tuple(config["action"]) != CASE_ACTIONS[kind]:
        raise ValueError("selected door act/side differs")
    if config["rate_hz"] != RATE_HZ or config["frame_count"] != FRAME_COUNT or tuple(config["cameras"]) != CAMERAS:
        raise ValueError("original camera or duration profile differs")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic door bundle passed: " + case)
        return
    raise ValueError("Surveyed Native hill-crest and original observed act required; diagnostic capture refused")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_and_action(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_diagnostic_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "diagnostic capture refused"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build() -> None:
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    exact = {row["case_id"] for row in json.loads(plan_bytes)["cases"]}
    from sys import path
    path.insert(0, str(HERE))
    from site_contract import CASE_ACTIONS
    rows = []
    for kind in KINDS:
        case = AID + "__" + kind
        if case not in exact:
            raise ValueError("selected exact case missing")
        config = {"law_id": "NRS-484B-153-2", "cell_id": "C102642",
                  "actor": "motor_vehicle_driver", "assignment_id": AID,
                  "selected_case_id": case, "action": CASE_ACTIONS[kind],
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "rate_hz": 20, "frame_count": 900,
                  "cameras": ["front", "rear", "left", "right"],
                  "diagnostic_only": True, "required_atoms": []}
        files = {"runner.py": RUNNER,
                 "site_contract.py": (HERE / "site_contract.py").read_text(),
                 "native_capture.py": (HERE / "native_capture.py").read_text(),
                 "door_interaction.py": (HERE / "door_interaction.py").read_text(),
                 "delivery_measure.py": (HERE / "delivery_measure.py").read_text(),
                 "delivery_audit.py": (HERE / "delivery_audit.py").read_text(),
                 "process_saved.py": (HERE / "process_saved.py").read_text(),
                 "compare_saved.py": (HERE / "compare_saved.py").read_text(),
                 "case-plan.json": plan_bytes.decode(),
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": {"status": "diagnostic_only_original_survey_pending",
                                                  "channels": config["cameras"]},
                        "files": [{"path": name, "content": content} for name, content in files.items()]}
        file = HERE / ("construction-" + kind + ".json")
        file.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": file.name,
                     "construction_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": "Door articulation and boarding/alighting actor realization require original Native review; no failure-triggered fallback selected"}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({"assignment_id": AID,
        "cases": rows, "status": "diagnostic_offline_only_surveyed_site_pending"}, indent=2) + "\n")
    print("built five exact diagnostic door-action constructions")


if __name__ == "__main__":
    build()
