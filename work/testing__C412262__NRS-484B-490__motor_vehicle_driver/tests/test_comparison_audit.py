"""Controlled pair proof rejects extra changes and absent original samples."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

from comparison_audit import audit
from highway_observations import sha
from highway_scene_construction import ASSIGNMENT, load_case


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def packet(self, variant):
        case_id = ASSIGNMENT + "__" + variant
        case = load_case(case_id)
        directory = self.root / variant
        directory.mkdir()
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id}
        context.update({key: case[key] for key in
                        ("highway_width_request", "device_request", "activity_request", "parking_location_request")})
        context.update({key: "same-original-source" for key in
                        ("dedication_sha256", "public_access_sha256", "person_identity_sha256", "vehicle_identity_sha256")})
        context_path = directory / "context.json"
        write(context_path, context)
        trace = directory / "trace.jsonl"
        trace.write_text("".join(json.dumps({"frame": i, "time_s": i / 20}) + "\n" for i in range(9)))
        receipt = directory / "receipt.json"
        write(receipt, {"case_id": case_id, "frame_count": 9,
                        "context_sha256": sha(context_path), "trace_sha256": sha(trace)})
        return {"case_id": case_id, "context": str(context_path),
                "trace": str(trace), "receipt": str(receipt)}

    def test_device_contrast_and_missing_trace(self):
        a = self.packet("park_narrow_device")
        b = self.packet("park_narrow_no_device")
        report = audit("park_narrow_no_device", a, b, diagnostic=True)
        self.assertEqual(report["declared_difference_checked"], ["device_request"])
        Path(b["trace"]).unlink()
        with self.assertRaisesRegex(ValueError, "missing independent original comparison source"):
            audit("park_narrow_no_device", a, b, diagnostic=True)

    def test_extra_change_rejected(self):
        a = self.packet("park_narrow_device")
        b = self.packet("park_wider_device")
        context_path = Path(b["context"])
        context = json.loads(context_path.read_text())
        context["activity_request"] = "stand"
        write(context_path, context)
        receipt_path = Path(b["receipt"])
        receipt = json.loads(receipt_path.read_text())
        receipt["context_sha256"] = sha(context_path)
        write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, "intervention differs"):
            audit("park_wider_device", a, b, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
