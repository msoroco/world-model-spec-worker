"""Build four exact C157964 source-gated Native bundles for pinned offline checks."""

import hashlib
import json
from pathlib import Path

from yield_view import CASES


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("yield_view.py", "reviewed_site.py", "native_capture.py",
           "saved_audit.py", "saved_finalizer.py", "comparison_audit.py")

RUNNER = '''"""Exact yield-sign Native entrypoint; a reviewed site and adapter are required."""
import argparse
import importlib
import json
from pathlib import Path

from native_capture import capture
from yield_view import CASES


def check(root):
    config = json.loads((root / "config.json").read_text())
    case = next((x for x in CASES if x.case_id == config["short_case_id"]), None)
    if case is None or config["selected_case_id"] != config["assignment_id"] + "__" + case.case_id:
        raise ValueError("selected exact yield case differs")
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-257-1", "C157964", "motor_vehicle_driver"):
        raise ValueError("yield law/cell/actor identity differs")
    if (config["approach_policy"], config["through_state"], config["officer_controls"]) != (
            case.approach_policy, case.through_state, case.officer_controls):
        raise ValueError("yield case controls differ")
    if config["frame_count"] != 900 or config["rate_hz"] != 20 or config["duration_s"] != 45:
        raise ValueError("Native capture profile differs")
    if set(config["camera_views"]) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four Native camera views differ")
    return config, case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--adapter-module")
    args = parser.parse_args()
    config, case = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    if not all((args.site, args.source_root, args.output_dir, args.adapter_module)):
        raise ValueError("reviewed original site, source root, Native adapter and output are required")
    adapter = importlib.import_module(args.adapter_module).create_adapter(config)
    print(json.dumps(capture(adapter, args.site, args.source_root, args.output_dir, case), sort_keys=True))


if __name__ == "__main__":
    main()
'''

TEST = '''import json
import tempfile
import unittest
from pathlib import Path

from runner import check


class ExactBundleTest(unittest.TestCase):
    def test_selected_identity_and_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        config, case = check(root)
        self.assertEqual(config["selected_case_id"], config["assignment_id"] + "__" + case.case_id)
        self.assertEqual(config["source_gate"], "reviewed_original_required")
        self.assertEqual(config["camera_views"], ["overview", "approach", "reference_corner", "driver_reference"])

    def test_changed_case_rejected(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp)
            value = json.loads((root / "config.json").read_text())
            value["selected_case_id"] += "-changed"
            (draft / "config.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "selected exact yield case differs"):
                check(draft)
'''


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def build():
    cases = []
    for case in CASES:
        case_id = ASSIGNMENT + "__" + case.case_id
        config = {
            "assignment_id": ASSIGNMENT, "selected_case_id": case_id,
            "short_case_id": case.case_id, "law_id": "NRS-484B-257-1",
            "cell_id": "C157964", "actor": "motor_vehicle_driver",
            "approach_policy": case.approach_policy,
            "through_state": case.through_state,
            "officer_controls": case.officer_controls,
            "frame_count": 900, "rate_hz": 20, "duration_s": 45,
            "camera_views": list(CAMERAS),
            "source_gate": "reviewed_original_required",
            "required_atoms": [], "source_packets": [],
            "cameras": [{"name": view} for view in CAMERAS],
            "case": {"case_id": case_id},
        }
        files = [{"path": "config.json", "content": json.dumps(config, sort_keys=True) + "\n"},
                 {"path": "runner.py", "content": RUNNER},
                 {"path": "tests/test_bundle.py", "content": TEST}]
        files += [{"path": name, "content": (ROOT / name).read_text()} for name in SOURCES]
        construction = {
            "case_id": case_id, "cell_id": "C157964", "actor": "motor_vehicle_driver",
            "law_id": "NRS-484B-257-1", "entrypoint": "runner.py",
            "files": files, "diagnostic_only": True,
            "physical_acceptance_claimed": False, "legal_judgment": None,
        }
        path = ROOT / "cases" / case.case_id / "construction.json"
        write_json(path, construction)
        cases.append({"case_id": case_id,
                      "construction": str(path.relative_to(ROOT)),
                      "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "diagnostic_only": True,
                      "candidate_risk": {"status": "none", "reason": "No reviewed alternate site geometry is available for a defensible fallback."}})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "diagnostic_only": True, "cases": cases,
                "comparisons": ["slow_vs_stop", "through_phase", "officer_exception"]}
    write_json(ROOT / "diagnostic-execution-manifest.json", manifest)
    print(json.dumps({"cases": len(cases), "manifest": str(ROOT / "diagnostic-execution-manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    build()
