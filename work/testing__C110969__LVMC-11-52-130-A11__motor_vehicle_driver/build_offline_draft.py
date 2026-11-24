"""Build seven exact source-bound diagnostic intersection constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = (
    "intersection_geometry.py", "stop_controller.py", "native_map.py",
    "original_capture.py", "native_bundle.py", "measure_gap.py",
    "saved_delivery.py", "comparison_audit.py",
)
CAMERAS = ["overview", "approach", "reference_corner", "driver_reference"]

RUNNER = '''"""Exact intersection capture through a reviewed operator-owned adapter."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
from saved_delivery import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(plan_bytes)
    case = config["selected_case_id"]
    entries = [row for row in plan["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    row = entries[0]
    for field in ("requested_front_body_gap_ft", "activity", "halt_cause"):
        if row[field] != config[field]:
            raise ValueError("Exact requested condition changed: " + field)
    if (config["law_id"], config["cell_id"], config["actor"]) != (plan["law_id"], plan["cell_id"], plan["actor"]):
        raise ValueError("Assignment identity changed")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("Original capture interval changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera contract changed")
    if config["source_requirements"] != ["reviewed_map_packet", "original_actor_pose", "original_context", "four_original_camera_png_streams"]:
        raise ValueError("Original source contract changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--map-packet")
    parser.add_argument("--adapter")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic exact intersection bundle passed: " + case)
        return
    if not args.output_dir or not args.map_packet or not args.adapter:
        raise ValueError("Reviewed map packet and operator-owned Native adapter required")
    from native_bundle import capture_bundle
    adapter = importlib.import_module(args.adapter)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Native adapter lacks owned open_session")
    with adapter.open_session(case, args.map_packet, args.host, args.port) as session:
        capture_bundle(
            session.world, session.ego, args.output_dir,
            map_packet_path=args.map_packet, case_id=case,
            attempt_id=session.attempt_id, recording_id=session.recording_id,
            world_to_local=session.world_to_local, read_camera=session.read_camera,
            read_context=session.read_context, acquisition_kind="original_native")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        self.assertEqual(runner.check(), config["selected_case_id"])

    def test_missing_original_sources_refused(self):
        with patch.object(sys, "argv", ["runner.py", "--output-dir", "/tmp/unused"]):
            with self.assertRaisesRegex(ValueError, "Reviewed map packet"):
                runner.main()

    def test_changed_plan_refused(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "case-plan.json"
        before = source.read_bytes()
        try:
            source.write_bytes(before + b"\\n")
            with self.assertRaisesRegex(ValueError, "Exact case plan changed"):
                runner.check()
        finally:
            source.write_bytes(before)


if __name__ == "__main__":
    unittest.main()
'''


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    entries = []
    for row in plan["cases"]:
        case = row["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": plan["law_id"],
            "cell_id": plan["cell_id"], "actor": plan["actor"],
            "selected_case_id": case,
            "requested_front_body_gap_ft": row["requested_front_body_gap_ft"],
            "activity": row["activity"], "halt_cause": row["halt_cause"],
            "plan_sha256": plan_sha, "rate_hz": 20,
            "frame_count": 900, "duration_s": 45, "cameras": CAMERAS,
            "source_requirements": ["reviewed_map_packet", "original_actor_pose", "original_context", "four_original_camera_png_streams"],
            "required_atoms": [], "source_packets": [], "diagnostic_only": True,
        }
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({"runner.py": RUNNER, "case-plan.json": plan_bytes.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": row["recording_description"],
            "files": [{"path": path, "content": content} for path, content in sorted(files.items())],
        }
        output = HERE / "cases" / suffix / "construction.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": case, "construction": str(output.relative_to(HERE)),
                        "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                        "candidate_risk": row["candidate_risk"]})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_site_pending",
        "cases": entries}, indent=2) + "\n")
    print("built", len(entries), "exact diagnostic intersection constructions")


if __name__ == "__main__":
    build()
