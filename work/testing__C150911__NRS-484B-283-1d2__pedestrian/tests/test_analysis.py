import hashlib
import importlib.util
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_countdown_crossing import MODULE, rows, site
import analysis
import delivery_audit
import comparison_audit


def write(path, value):
    path.write_text(json.dumps(value) + "\n")


class SavedAnalysis(unittest.TestCase):
    def fixture(self, attempt, case=None, completion_index=4):
        case = case or MODULE.CASES[0]
        cid = "testing__C150911__NRS-484B-283-1d2__pedestrian__" + case.case_id
        write(attempt / "config.json", {"selected_case_id": cid,
            "law_id": "NRS-484B-283-1d2", "cell_id": "C150911",
            "actor": "pedestrian", "case": {"recording_description": {
                "channels": [{"name": name, "unit": "original"} for name in (
                    "signal_countdown", "pedestrian_crossing", "highway_context",
                    "exception_context")]}}})
        frames = rows(case, completion_index)
        for row in frames:
            row["position_m"] = [*row["pedestrian_xy"], 0.0]
            row["exception_context"] = {"NRS 484B.287": "unresolved",
                "NRS 484B.290": "unresolved", "NRS 484B.350": "unresolved"}
            row["in_highway"] = 102 <= row["original_frame"] < 100 + completion_index
            row["crossing_complete"] = row["original_frame"] >= 100 + completion_index
        packet = {"assignment_id": "testing__C150911__NRS-484B-283-1d2__pedestrian",
            "case_id": cid, "original_trace_id": "synthetic-fixture",
            "diagnostic_fixture": True, "site": site(), "frames": frames}
        write(attempt / analysis.SOURCE, packet)
        write(attempt / analysis.RECEIPT, {"case_id": cid, "fps": 20,
            "frame_count": len(frames),
            "diagnostic_fixture": True,
            "source_sha256": hashlib.sha256((attempt / analysis.SOURCE).read_bytes()).hexdigest()})
        with (attempt / "trace.jsonl").open("w") as trace, (attempt / "video_frames.jsonl").open("w") as fmap:
            for i, frame in enumerate(frames):
                trace.write(json.dumps({"frame": frame["original_frame"],
                    "time_s": frame["time_s"],
                    "position_m": frame["position_m"]}) + "\n")
                fmap.write(json.dumps({"video_frame": i,
                    "native_frame": frame["original_frame"],
                    "carla_frame": frame["original_frame"],
                    "time_s": frame["time_s"]}) + "\n")
        for name in analysis.CAMERAS:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=20",
                "-frames:v", "8", "-c:v", "ffv1",
                str(attempt / (name + ".mkv"))], check=True,
                capture_output=True)
        return cid

    def test_saved_only_sources_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            cid = self.fixture(attempt)
            report = analysis.analyze(attempt, attempt / "analysis.json")
            self.assertEqual(report["case_id"], cid)
            self.assertEqual(report["measurements"]["zero_boundary"]["value"]["completion_relation"], "before_zero")
            self.assertTrue((attempt / "result.json").is_file())
            audit = delivery_audit.audit(attempt, cid, diagnostic=True)
            self.assertEqual(audit["completion_relation"], "before_zero")
            self.assertEqual(len(audit["full_video_decode"]), 4)
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            self.fixture(attempt)
            (attempt / analysis.SOURCE).unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                analysis.analyze(attempt, attempt / "analysis.json")

    def test_independent_comparison_isolation(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            a, b = Path(left), Path(right)
            self.fixture(a, MODULE.CASES[0], 4)
            self.fixture(b, MODULE.CASES[1], 5)
            result = comparison_audit.compare("completion_before_at", a, b, diagnostic=True)
            self.assertTrue(result["passed"])
            packet_path = b / analysis.SOURCE
            packet = json.loads(packet_path.read_text())
            packet["site"]["highway_source_sha256"] = "changed"
            write(packet_path, packet)
            receipt_path = b / analysis.RECEIPT
            receipt = json.loads(receipt_path.read_text())
            receipt["source_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            write(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "fixed original site differs"):
                comparison_audit.compare("completion_before_at", a, b, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
