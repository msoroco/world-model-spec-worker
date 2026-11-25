import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import finalizer
from test_officer_saved_review import capture_and_review, sha, sources, write


class OfficerFinalizerTests(unittest.TestCase):
    def _attempt(self, attempt):
        review_root = attempt / "source_review"
        review_root.mkdir()
        packet = sources(review_root)
        road = review_root / "road.txt"
        road.write_text((ROOT / "officer-site.xodr").read_text())
        value = json.loads(packet.read_text())
        value["sources"]["road"]["sha256"] = sha(road)
        packet = write(review_root / "source-packet.json", value)
        for name in ("config.json", "runner.py", "construction.json", "officer-site.xodr"):
            shutil.copy2(ROOT / name, attempt / name)
        case_id = json.loads((attempt / "config.json").read_text())["selected_case_id"]
        capture, review = capture_and_review(attempt, packet, case_id=case_id)
        shutil.copy2(capture, attempt / "capture-receipt.json")
        shutil.copy2(review, attempt / "officer_review.json")
        rows = json.loads(capture.read_text())["rows"]
        with (attempt / "video_frames.jsonl").open("w") as stream:
            for index, row in enumerate(rows):
                stream.write(json.dumps({"video_frame": index,
                                         "carla_frame": row["carla_frame"],
                                         "time_s": row["native_actor_source"]["time_s"],
                                         "native_frame": row["carla_frame"]}) + "\n")
        with (attempt / "trace.jsonl").open("w") as stream:
            for row in rows:
                stream.write(json.dumps({"frame": row["carla_frame"],
                                         "time_s": row["native_actor_source"]["time_s"]}) + "\n")
        (attempt / "capture").mkdir()
        with (attempt / "capture/evidence.jsonl").open("w") as stream:
            for row in rows:
                stream.write(json.dumps({"original_frame": row["carla_frame"]}) + "\n")
        return capture

    def test_saved_only_channels_and_original_frame_join(self):
        with tempfile.TemporaryDirectory() as dirname:
            attempt = Path(dirname) / "attempt"
            attempt.mkdir()
            self._attempt(attempt)
            observed = []

            def assessor(root, result):
                observed.append(result)
                result["physical_checks"] = {"setup": {"status": "unverified"}}
                return result

            def writer(root, result):
                write(root / "result.json", result)

            report = finalizer.finalize(attempt, attempt / "analysis.json",
                                        assessor=assessor, writer=writer)
            self.assertTrue(report["analysis_complete"])
            self.assertEqual(report["legal_conclusion"], "unresolved")
            self.assertEqual(set(report["measurements"]),
                             {"signed_entrance", "officer_control", "officer_direction",
                              "other_traffic", "ego_response"})
            self.assertTrue(report["measurements"]["signed_entrance"]["value"]["non_through_highway"])
            self.assertEqual(report["measurements"]["other_traffic"]["value"]["immediate_hazard_judgment"],
                             "unresolved")
            self.assertEqual(len(observed[0]["recording_evidence"]),
                             len(json.loads((attempt / "config.json").read_text())
                                 ["recording_description"]["channels"]) + 1)
            self.assertEqual(len((attempt / "channels/officer_direction_observed.jsonl").read_text().splitlines()), 3)
            with self.assertRaisesRegex(ValueError, "Retain prior saved finalization"):
                finalizer.finalize(attempt, attempt / "analysis.json",
                                   assessor=assessor, writer=writer)

    def test_missing_source_and_changed_original_frame_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            attempt = Path(dirname) / "attempt"
            attempt.mkdir()
            self._attempt(attempt)
            (attempt / "capture/evidence.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                finalizer.finalize(attempt, attempt / "analysis.json")
            with (attempt / "capture/evidence.jsonl").open("w") as stream:
                for frame in (100, 999, 102):
                    stream.write(json.dumps({"original_frame": frame}) + "\n")
            with self.assertRaisesRegex(ValueError, "frame join differs"):
                finalizer.finalize(attempt, attempt / "analysis.json")

    def test_real_cpu_physical_assessor_keeps_fixture_unconfirmed(self):
        with tempfile.TemporaryDirectory() as dirname:
            attempt = Path(dirname) / "attempt"
            attempt.mkdir()
            self._attempt(attempt)
            report = finalizer.finalize(attempt, attempt / "analysis.json")
            result = json.loads((attempt / "result.json").read_text())
            self.assertTrue(report["analysis_complete"])
            self.assertFalse(result["setup_confirmed"])
            self.assertEqual(result["physical_checks"]["setup"]["status"], "not_met")
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["provenance_kind"], "synthetic_fixture")


if __name__ == "__main__":
    unittest.main()
