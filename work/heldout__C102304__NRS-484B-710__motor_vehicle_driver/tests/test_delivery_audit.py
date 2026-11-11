import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

folder = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("delivery_audit", folder / "delivery_audit.py")
auditor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = auditor
spec.loader.exec_module(auditor)
finalizer = auditor._finalizer()


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        config = {"law_id": "NRS-484B-710", "selected_case_id": "fire-at-500",
                  "fire_branch": "traveling_follow"}
        context = {"alarm_response_source": "authored dispatch premise",
                   "apparatus_answered_alarm": True,
                   "subject_authorized_emergency": False,
                   "subject_official_business": False}
        (self.root / "config.json").write_text(json.dumps(config))
        (self.root / "fire_context.json").write_text(json.dumps(context))
        def box(a, b):
            return [[a, -1], [b, -1], [b, 1], [a, 1]]
        rows = {
            "video_frames.jsonl": [{"video_frame": i, "carla_frame": 20+i, "time_s": i/20}
                                   for i in range(2)],
            "trace.jsonl": [{"frame": 20+i, "time_s": i/20} for i in range(2)],
            "participant_footprints.jsonl": [
                {"frame": 20+i, "time_s": i/20, "ego_id": "ego", "apparatus_id": "fire",
                 "ego_corners": box(i, i+4),
                 "apparatus_corners": box(i+4+500/3.280839895013123,
                                           i+10+500/3.280839895013123)} for i in range(2)],
            "participant_state.jsonl": [
                {"frame": 20+i, "time_s": i/20, "apparatus_moving": True,
                 "ego_moving": True, "ego_following": True, "ego_parked": False,
                 "warning_lamp": True, "siren": None} for i in range(2)]}
        for name, value in rows.items():
            (self.root / name).write_text("".join(json.dumps(row)+"\n" for row in value))
        for camera in auditor.CAMERAS:
            (self.root / (camera + ".mkv")).write_bytes(b"fixture camera " + camera.encode())
        self.report = finalizer.analyze(self.root)

    def decoder(self, path, count, **kwargs):
        self.assertEqual(count, 2)
        return {"frames": count, "full_decode": True}

    def test_recomputes_saved_measurement_and_all_four_sources(self):
        result = auditor.audit_attempt(self.root, self.report, decoder=self.decoder)
        self.assertTrue(result["measurement_recomputed"])
        self.assertEqual(set(result["camera_decodes"]), set(auditor.CAMERAS))
        self.assertFalse(result["physical_visibility_claimed"])

    def test_rejects_changed_original_and_missing_camera(self):
        source = self.root / "participant_state.jsonl"
        source.write_text(source.read_text().replace('"ego_following": true',
                                                     '"ego_following": false'))
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            auditor.audit_attempt(self.root, self.report, decoder=self.decoder)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "Missing audited original source"):
            auditor.audit_attempt(self.root, self.report, decoder=self.decoder)

    def test_rejects_missing_camera_and_bad_decode_count(self):
        (self.root / "approach.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "Missing named original camera"):
            auditor.audit_attempt(self.root, self.report, decoder=self.decoder)
        (self.root / "approach.mkv").write_bytes(b"restored fixture")
        with self.assertRaisesRegex(ValueError, "full decode frame count"):
            auditor.audit_attempt(self.root, self.report,
                                  decoder=lambda *_args, **_kwargs: {"frames": 1})


if __name__ == "__main__":
    unittest.main()
