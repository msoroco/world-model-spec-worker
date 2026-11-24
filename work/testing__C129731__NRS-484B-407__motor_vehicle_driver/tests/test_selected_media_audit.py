import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import capture
from selected_media_audit import audit_selected, audit_selected_pair
from selected_media_audit import audit_acquired
from original_source_acquisition import acquire
from saved_media_decode import decode_selected, pixel_presence
from delivery_audit import review as review_delivery
from test_native_sight_capture import CASE, NativeAdapter


RECORDING = hashlib.sha256(b"diagnostic selected recording").hexdigest()
CLEAR_RECORDING = hashlib.sha256(b"diagnostic clear recording").hexdigest()
CLEAR_CASE = CASE.replace("curve_ahead_blocked", "curve_clear")


class SelectedMediaAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.attempt = cls.root / "attempt"
        capture(NativeAdapter(), CASE, cls.attempt, recording_id=RECORDING)
        cls.video = cls.root / "diagnostic.mkv"
        command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                   "testsrc2=s=16x16:r=20", "-frames:v", "900", "-c:v", "mpeg4",
                   str(cls.video)]
        subprocess.run(command, check=True, capture_output=True)
        cls.trace = cls.root / "trace.json"
        cls.trace.write_text('{"kind":"diagnostic-only"}\n')
        meta_rel = Path("accepted") / RECORDING / "metadata.json"
        meta_path = cls.root / meta_rel
        meta_path.parent.mkdir(parents=True)
        original_video = meta_path.parent / "raw.mkv"
        original_trace = meta_path.parent / "trace.json"
        shutil.copyfile(cls.video, original_video)
        shutil.copyfile(cls.trace, original_trace)
        archive = meta_path.parent / "delivery-audit-completed.json"
        archive.write_text(json.dumps({"format": "worker-delivery-audit", "passed": True,
                                       "case_id": CASE, "recording_id": RECORDING,
                                       "job_id": 17, "attempt": 1, "frames": 900,
                                       "video_sha256": hashlib.sha256(cls.video.read_bytes()).hexdigest(),
                                       "trace_sha256": hashlib.sha256(cls.trace.read_bytes()).hexdigest(),
                                       "checks": {name: True for name in
                                                  ("native_source", "all_participants", "time_join",
                                                   "full_video_decode", "actual_pixels",
                                                   "physical_completion")}}) + "\n")
        meta_path.write_text(json.dumps({"recording_id": RECORDING, "case_id": CASE,
                                         "status": "accepted", "frames": 900,
                                         "job_id": 17, "attempt": 1,
                                         "video_sha256": hashlib.sha256(cls.video.read_bytes()).hexdigest(),
                                         "trace_sha256": hashlib.sha256(cls.trace.read_bytes()).hexdigest(),
                                         "acceptance": {"case_id": CASE,
                                                        "video_source": str(original_video),
                                                        "video_sha256": hashlib.sha256(cls.video.read_bytes()).hexdigest(),
                                                        "trace_source": str(original_trace),
                                                        "trace_sha256": hashlib.sha256(cls.trace.read_bytes()).hexdigest(),
                                                        "delivery_audit": str(archive),
                                                        "delivery_audit_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}) + "\n")
        cls.plan = {"accepted_reuse_candidates": [{"case_id": CASE, "recording_id": RECORDING}],
                    "sources": [{"path": str(meta_rel),
                                 "sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest()}]}
        cls.clear_attempt = cls.root / "clear-attempt"
        clear_adapter = NativeAdapter()
        clear_adapter.blocked_direction = None
        capture(clear_adapter, CLEAR_CASE, cls.clear_attempt, recording_id=CLEAR_RECORDING)
        cls.clear_video = cls.root / "clear.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=white:s=16x16:r=20", "-frames:v", "900", "-c:v", "mpeg4",
                        str(cls.clear_video)], check=True, capture_output=True)
        cls.clear_trace = cls.root / "clear-trace.json"
        cls.clear_trace.write_text('{"kind":"diagnostic-clear"}\n')
        clear_rel = Path("accepted") / CLEAR_RECORDING / "metadata.json"
        clear_meta = cls.root / clear_rel
        clear_meta.parent.mkdir(parents=True)
        clear_meta.write_text(json.dumps({"recording_id": CLEAR_RECORDING, "case_id": CLEAR_CASE,
                                          "status": "accepted", "frames": 900,
                                          "video_sha256": hashlib.sha256(cls.clear_video.read_bytes()).hexdigest(),
                                          "trace_sha256": hashlib.sha256(cls.clear_trace.read_bytes()).hexdigest()}) + "\n")
        cls.plan["accepted_reuse_candidates"].append({"case_id": CLEAR_CASE,
                                                       "recording_id": CLEAR_RECORDING})
        cls.plan["sources"].append({"path": str(clear_rel),
                                    "sha256": hashlib.sha256(clear_meta.read_bytes()).hexdigest()})
        cls.plan["accepted_comparisons_pending_original_review"] = [{
            "comparison_id": "curve_ahead_opposing",
            "case_ids": [CLEAR_CASE, CASE],
            "recording_ids": [CLEAR_RECORDING, RECORDING]}]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exact_selected_source_media_and_sight_join(self):
        result = audit_selected(self.plan, self.root, self.attempt, self.video, self.trace)
        self.assertEqual(result["recording_id"], RECORDING)
        self.assertEqual(result["decoded_video_frames"], 900)
        self.assertEqual(result["sight_measurement"]["original_frames"], 900)
        self.assertEqual(result["canonical_acceptance"], "unresolved")

    def test_wrong_recording_or_metadata_hash_rejected(self):
        plan = json.loads(json.dumps(self.plan))
        plan["accepted_reuse_candidates"][0]["recording_id"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity absent"):
            audit_selected(plan, self.root, self.attempt, self.video, self.trace)
        plan = json.loads(json.dumps(self.plan))
        plan["sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "metadata source hash"):
            audit_selected(plan, self.root, self.attempt, self.video, self.trace)

    def test_missing_and_stale_original_trace_rejected(self):
        with self.assertRaisesRegex(ValueError, "source missing"):
            audit_selected(self.plan, self.root, self.attempt, self.video, self.root / "absent.json")
        tampered = self.root / "changed-trace.json"
        tampered.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "trace hash mismatch"):
            audit_selected(self.plan, self.root, self.attempt, self.video, tampered)

    def test_pair_joins_distinct_media_to_measured_difference(self):
        left = (self.clear_attempt, self.clear_video, self.clear_trace)
        right = (self.attempt, self.video, self.trace)
        result = audit_selected_pair(self.plan, self.root, "curve_ahead_opposing", left, right)
        self.assertEqual(result["comparison"]["recording_ids"], [CLEAR_RECORDING, RECORDING])
        self.assertEqual(result["selected_media"][0]["decoded_video_frames"], 900)
        self.assertEqual(result["canonical_acceptance"], "unresolved")

    def test_pair_rejects_reused_media_bytes(self):
        plan = json.loads(json.dumps(self.plan))
        clear_meta = self.root / plan["sources"][1]["path"]
        original = json.loads(clear_meta.read_text())
        try:
            changed = dict(original, video_sha256=hashlib.sha256(self.video.read_bytes()).hexdigest())
            clear_meta.write_text(json.dumps(changed) + "\n")
            plan["sources"][1]["sha256"] = hashlib.sha256(clear_meta.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "reused video"):
                audit_selected_pair(plan, self.root, "curve_ahead_opposing",
                                    (self.clear_attempt, self.video, self.clear_trace),
                                    (self.attempt, self.video, self.trace))
        finally:
            clear_meta.write_text(json.dumps(original) + "\n")

    def test_acquire_original_bytes_and_reaudit_copy(self):
        target = self.root / "acquired"
        receipt = acquire(self.plan, self.root, CASE, RECORDING, target)
        self.assertEqual(receipt["recording_id"], RECORDING)
        result = audit_acquired(self.plan, self.root, self.attempt, target)
        self.assertEqual(result["decoded_video_frames"], 900)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            acquire(self.plan, self.root, CASE, RECORDING, target)
        (target / "trace.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "acquired original source hash"):
            audit_acquired(self.plan, self.root, self.attempt, target)

    def test_acquire_rejects_missing_original_source(self):
        plan = json.loads(json.dumps(self.plan))
        meta_path = self.root / plan["sources"][0]["path"]
        original = json.loads(meta_path.read_text())
        try:
            changed = json.loads(json.dumps(original))
            changed["acceptance"]["video_source"] = str(meta_path.parent / "missing" / "raw.mkv")
            meta_path.write_text(json.dumps(changed) + "\n")
            plan["sources"][0]["sha256"] = hashlib.sha256(meta_path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "original video source missing"):
                acquire(plan, self.root, CASE, RECORDING, self.root / "not-acquired")
        finally:
            meta_path.write_text(json.dumps(original) + "\n")

    def test_full_saved_decode_binds_frame_map_and_pixels(self):
        target = self.root / "decode-acquired"
        acquire(self.plan, self.root, CASE, RECORDING, target)
        receipt = self.root / "source-decode.json"
        decoded = decode_selected(self.plan, self.root, self.attempt, target, receipt)
        self.assertEqual(decoded["recording_id"], RECORDING)
        self.assertEqual(json.loads(receipt.read_text())["frames"], 900)
        self.assertEqual(decoded["physical_visibility_judgment"], "unresolved")
        from worker_exchange.media import verify_receipt
        with self.assertRaisesRegex(ValueError, "Stale/incompatible"):
            verify_receipt(target / "raw.mkv", receipt, 900,
                           mapping_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            decode_selected(self.plan, self.root, self.attempt, target, receipt)

    def test_flat_decoded_frame_rejected(self):
        from collections import namedtuple
        Frame = namedtuple("Frame", "width height pixels")
        with self.assertRaisesRegex(ValueError, "varied pixels"):
            pixel_presence(Frame(16, 16, bytes(16 * 16 * 3)))

    def test_selected_archived_delivery_review_is_not_new_acceptance(self):
        target = self.root / "delivery-acquired"
        acquire(self.plan, self.root, CASE, RECORDING, target)
        receipt = self.root / "delivery-decode.json"
        decode_selected(self.plan, self.root, self.attempt, target, receipt)
        result = review_delivery(self.plan, self.root, self.attempt, target, receipt)
        self.assertEqual(result["law_specific_visibility_review"], "unresolved")
        self.assertEqual(result["canonical_acceptance"], "not_performed_here")
        archive = self.root / "accepted" / RECORDING / "delivery-audit-completed.json"
        original = archive.read_bytes()
        try:
            archive.write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "archived delivery audit hash"):
                review_delivery(self.plan, self.root, self.attempt, target, receipt)
        finally:
            archive.write_bytes(original)

    def test_selected_delivery_command_positive_and_wrong_attempt(self):
        plan_file = self.root / "diagnostic-plan.json"
        plan_file.write_text(json.dumps(self.plan) + "\n")
        script = Path(__file__).resolve().parents[1] / "selected_delivery.py"
        bundle = self.root / "cli-original"
        decode = self.root / "cli-decode.json"
        output = self.root / "cli-review.json"
        args = [sys.executable, str(script), "--plan", str(plan_file),
                "--repository", str(self.root), "--case", CASE,
                "--recording", RECORDING, "--sight-attempt", str(self.attempt),
                "--source-bundle", str(bundle), "--decode-receipt", str(decode),
                "--review-output", str(output)]
        subprocess.run(args, check=True, capture_output=True)
        self.assertEqual(json.loads(output.read_text())["canonical_acceptance"],
                         "not_performed_here")
        wrong = list(args)
        wrong[wrong.index("--sight-attempt") + 1] = str(self.clear_attempt)
        wrong[wrong.index("--source-bundle") + 1] = str(self.root / "wrong-original")
        wrong[wrong.index("--decode-receipt") + 1] = str(self.root / "wrong-decode.json")
        wrong[wrong.index("--review-output") + 1] = str(self.root / "wrong-review.json")
        rejected = subprocess.run(wrong, capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("selected sight attempt identity mismatch", rejected.stderr)
        self.assertFalse((self.root / "wrong-original").exists())


if __name__ == "__main__":
    unittest.main()
