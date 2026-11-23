import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from candidate_opendrive import build
from delivery_audit import audit_source_chain, verify_decode_receipt
from reviewed_context import REQUIRED
from stand_route import make
from taxi_cameras import NAMES
from taxi_native_motion import route_points
from test_turn_trace_finalizer import interpolate_path
from turn_trace_finalizer import ASSIGNMENT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.layout = self.root / "layout.json"
        self.layout.write_text(json.dumps(make("near_stand")))
        self.map = self.root / "map.xodr"
        self.map.write_bytes(build("near_stand"))
        review = self.root / "reviewed_sources"
        review.mkdir()
        sources = {}
        for kind in REQUIRED:
            source = review / (kind + ".txt")
            quote = "synthetic fixture " + kind
            source.write_text(quote + "\n")
            sources[kind] = {"path": "reviewed_sources/" + source.name,
                             "sha256": sha(source), "record_id": "fixture-" + kind,
                             "review_note": "synthetic CPU fixture only", "quote": quote}
        layout = make("near_stand")
        context = {"format": "c150530-reviewed-context-v1", "assignment_id": ASSIGNMENT,
                   "case_id": ASSIGNMENT + "__near_stand", "law_id": "LVMC-11-60-090",
                   "actor": "taxi_driver", "map_sha256": sha(self.map),
                   "stand_center_m": layout["stand"]["center"],
                   "notice_point_m": layout["posted_notice"]["point"],
                   "notice_meaning": "right turn at first street intersection",
                   "sources": sources}
        (self.root / "reviewed-context.json").write_text(json.dumps(context))
        self.motion = interpolate_path(route_points(layout), "near_stand")
        self.write_motion()
        self.required = ("original-trace.jsonl", "original-trace-seal.json",
                         "reviewed-context.json", "video_frames.jsonl", "trace.jsonl",
                         "taxi-controller-history.jsonl", "config.json",
                         "construction.json", "runner.py", *(name + ".mkv" for name in NAMES))
        for name in ("config.json", "construction.json", "runner.py"):
            (self.root / name).write_text("fixture " + name + "\n")
        for name in NAMES:
            (self.root / (name + ".mkv")).write_bytes(b"fixture video " + name.encode())
        self.seal()

    def write_motion(self):
        root = self.root
        (root / "original-trace.jsonl").write_text("".join(
            json.dumps(row) + "\n" for row in self.motion))
        (root / "video_frames.jsonl").write_text("".join(
            json.dumps({"video_frame": index, "carla_frame": row["frame"],
                        "native_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
            for index, row in enumerate(self.motion)))
        for name in ("trace.jsonl", "taxi-controller-history.jsonl"):
            (root / name).write_text("".join(
                json.dumps({"frame": row["frame"], "time_s": row["time_s"]}) + "\n"
                for row in self.motion))
        trace = root / "original-trace.jsonl"
        packet = root / "reviewed-context.json"
        (root / "original-trace-seal.json").write_text(json.dumps({
            "format": "c150530-original-trace-seal-v1", "case_id": ASSIGNMENT + "__near_stand",
            "rate_hz": 20, "trace_sha256": sha(trace), "context_packet_sha256": sha(packet),
            "map_sha256": sha(self.map), "frame_count": len(self.motion),
            "first_frame": self.motion[0]["frame"], "last_frame": self.motion[-1]["frame"]}))

    def seal(self):
        sources = {name: sha(self.root / name) for name in self.required}
        (self.root / "capture-seal.json").write_text(json.dumps({
            "format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": False, "frames": len(self.motion),
            "restoration": {"restored": True},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "encoder_exit_codes": {name: 0 for name in NAMES},
            "physical_acceptance_claimed": False, "sources": sources,
            "native_revision": {"construction_sha256": sources["construction.json"],
                                "runner_sha256": sources["runner.py"]}}))

    def audit(self):
        return audit_source_chain(self.root, "near_stand", self.map, self.layout)

    def test_complete_source_chain_joins_all_frames(self):
        result = self.audit()
        self.assertEqual(result["frames"], len(self.motion))
        self.assertTrue(result["measurement"]["engineering_right_turn_observed"])
        self.assertFalse(result["physical_or_pixel_acceptance"])

    def test_changed_camera_bytes_rejected(self):
        (self.root / "approach.mkv").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "seal source differs: approach.mkv"):
            self.audit()

    def test_missing_camera_rejected(self):
        (self.root / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "missing or escaping original source"):
            self.audit()

    def test_altered_frame_map_rejected_even_with_updated_seal(self):
        path = self.root / "video_frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[5]["carla_frame"] += 1
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.seal()
        with self.assertRaisesRegex(ValueError, "frame-map identity differs"):
            self.audit()

    def test_short_control_history_rejected_even_with_updated_seal(self):
        path = self.root / "taxi-controller-history.jsonl"
        path.write_text("".join(path.read_text().splitlines(keepends=True)[:-1]))
        self.seal()
        with self.assertRaisesRegex(ValueError, "acquisition frame join differs"):
            self.audit()

    def test_incomplete_restoration_rejected(self):
        path = self.root / "capture-seal.json"
        seal = json.loads(path.read_text())
        seal["restoration"]["restored"] = False
        path.write_text(json.dumps(seal))
        with self.assertRaisesRegex(ValueError, "capture seal incomplete"):
            self.audit()

    def test_stale_full_decode_receipt_rejected(self):
        result = self.audit()
        (self.root / "raw.mkv").write_bytes(b"composed fixture")
        auditor = self.root / "media.py"
        auditor.write_text("fixture media auditor\n")
        receipt = self.root / "decode.json"
        composition = self.root / "four-view-receipt.json"
        composition.write_text(json.dumps({
            "format": "synchronized-four-view",
            "sources": {name: sha(self.root / (name + ".mkv")) for name in NAMES},
            "frame_map_sha256": result["frame_map_sha256"],
            "primary_sha256": sha(self.root / "raw.mkv"),
            "frames": len(self.motion)}))
        receipt.write_text(json.dumps({"format": "source-decode", "passed": True,
            "video_sha256": sha(self.root / "raw.mkv"), "frames": len(self.motion),
            "mapping_sha256": result["frame_map_sha256"],
            "auditor_sha256": sha(auditor),
            "checks": {"frame_count": "all-decoded-frames"}}))
        self.assertTrue(verify_decode_receipt(result, self.root, receipt, composition, auditor)["passed"])
        (self.root / "raw.mkv").write_bytes(b"stale composed fixture")
        with self.assertRaisesRegex(ValueError, "not joined to four sealed sources"):
            verify_decode_receipt(result, self.root, receipt, composition, auditor)
        composition_data = json.loads(composition.read_text())
        composition_data["primary_sha256"] = sha(self.root / "raw.mkv")
        composition.write_text(json.dumps(composition_data))
        with self.assertRaisesRegex(ValueError, "current full-decode receipt"):
            verify_decode_receipt(result, self.root, receipt, composition, auditor)

    def test_composition_cannot_swap_camera(self):
        result = self.audit()
        (self.root / "raw.mkv").write_bytes(b"composed fixture")
        auditor = self.root / "media.py"
        auditor.write_text("fixture media auditor\n")
        receipt = self.root / "decode.json"
        receipt.write_text("{}")
        composition = self.root / "four-view-receipt.json"
        composition.write_text(json.dumps({
            "format": "synchronized-four-view",
            "sources": {name: "0" * 64 for name in NAMES},
            "frame_map_sha256": result["frame_map_sha256"],
            "primary_sha256": sha(self.root / "raw.mkv"),
            "frames": len(self.motion)}))
        with self.assertRaisesRegex(ValueError, "not joined to four sealed sources"):
            verify_decode_receipt(result, self.root, receipt, composition, auditor)


if __name__ == "__main__":
    unittest.main()
