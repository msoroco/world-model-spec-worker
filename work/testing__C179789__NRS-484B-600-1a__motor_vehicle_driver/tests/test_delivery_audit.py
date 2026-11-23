"""Full-decode delivery-audit diagnostics; generated pixels are not CARLA evidence."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit
from native_media import encode, sha
from saved_measurement import finalize_attempt
from test_saved_measurement import fixture


VIEWS = (("overview", 2, 2), ("approach", 2, 2),
         ("reference_corner", 2, 2), ("driver_reference", 2, 2))


def video_fixture(attempt: Path):
    fixture(attempt)
    trace_path, map_path = attempt / "trace.jsonl", attempt / "video_frames.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    mapping = [json.loads(line) for line in map_path.read_text().splitlines()]
    files = {name: [] for name, _, _ in VIEWS}
    pixels = bytes((0, 0, 0, 255, 25, 0, 0, 255,
                    0, 25, 0, 255, 0, 0, 25, 255))
    digest = hashlib.sha256(pixels).hexdigest()
    for index, row in enumerate(trace):
        frame, time_s = row["frame"], row["time_s"]
        row["leader_position_m"] = [row["position_m"][0] + 30, 0, 0]
        for name, width, height in VIEWS:
            path = attempt / "raw" / name / f"{frame}.bgra"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pixels)
            files[name].append(path)
            row["camera_sources"][name] = {
                "frame": frame, "time_s": time_s, "width": width, "height": height,
                "raw_bgra": f"{name}/{frame}.bgra", "sha256": digest}
            mapping[index]["camera_source_sha256"][name] = digest
    trace_path.write_text("".join(json.dumps(row) + "\n" for row in trace))
    map_path.write_text("".join(json.dumps(row) + "\n" for row in mapping))
    videos = {}
    for name, width, height in VIEWS:
        path = attempt / (name + ".mkv")
        path.unlink()
        encode(files[name], width, height, path)
        videos[name] = sha(path)
    media_path = attempt / "media-receipt.json"
    media = json.loads(media_path.read_text())
    media.update(trace_sha256=sha(trace_path), frame_map_sha256=sha(map_path),
                 video_sha256=videos)
    media_path.write_text(json.dumps(media))
    (attempt / "native-run-status.json").write_text(json.dumps({
        "case_id": json.loads((attempt / "authored-setup.json").read_text())["case_id"],
        "capture": {"frames": 900}, "restoration": {"restored": True},
        "errors": [], "physical_acceptance_claimed": False}))
    finalize_attempt(attempt, attempt / "analysis-report.json")


class DeliveryAuditTests(unittest.TestCase):
    def test_full_decode_and_source_mutations(self):
        root = HERE.parents[1] / ".runtime-work"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            attempt = Path(directory) / "attempt"
            video_fixture(attempt)
            result = audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)
            self.assertEqual(result["frame_count"], 900)
            self.assertTrue(result["checks"]["full_video_decode"])
            self.assertFalse(result["participant_visibility_verified"])
            self.assertFalse(result["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "diagnostic camera override"):
                audit(attempt, diagnostic_views=VIEWS)
            video = attempt / "overview.mkv"
            original = video.read_bytes()
            video.write_bytes(original + b"changed")
            with self.assertRaisesRegex(ValueError, "stale saved analysis source"):
                audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)
            video.write_bytes(original)
            result_path = attempt / "result.json"
            saved = json.loads(result_path.read_text())
            saved["measured_values"]["steady_means"]["ego_speed_mps"] = 99
            result_path.write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "saved measurement differs"):
                audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)

    def test_missing_participant_and_failed_restoration_rejected(self):
        root = HERE.parents[1] / ".runtime-work"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            attempt = Path(directory) / "attempt"
            video_fixture(attempt)
            status_path = attempt / "native-run-status.json"
            status = json.loads(status_path.read_text())
            status["restoration"]["restored"] = False
            status_path.write_text(json.dumps(status))
            with self.assertRaisesRegex(ValueError, "restoration differs"):
                audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)
            status["restoration"]["restored"] = True
            status_path.write_text(json.dumps(status))
            trace_path = attempt / "trace.jsonl"
            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
            rows[5].pop("leader_position_m")
            trace_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            media_path = attempt / "media-receipt.json"
            media = json.loads(media_path.read_text())
            media["trace_sha256"] = sha(trace_path)
            media_path.write_text(json.dumps(media))
            report_path = attempt / "analysis-report.json"
            report = json.loads(report_path.read_text())
            report["sources"]["trace.jsonl"] = sha(trace_path)
            report["sources"]["media-receipt.json"] = sha(media_path)
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "missing original participant position"):
                audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)

    def test_rehashed_changed_video_pixels_rejected(self):
        root = HERE.parents[1] / ".runtime-work"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            attempt = Path(directory) / "attempt"
            video_fixture(attempt)
            video = attempt / "overview.mkv"
            video.unlink()
            replacement = bytes((0, 0, 0, 255, 40, 0, 0, 255,
                                 0, 40, 0, 255, 0, 0, 40, 255))
            source = attempt / "changed.bgra"
            source.write_bytes(replacement)
            encode([source] * 900, 2, 2, video)
            media_path = attempt / "media-receipt.json"
            media = json.loads(media_path.read_text())
            media["video_sha256"]["overview"] = sha(video)
            media_path.write_text(json.dumps(media))
            report_path = attempt / "analysis-report.json"
            report = json.loads(report_path.read_text())
            report["sources"]["overview.mkv"] = sha(video)
            report["sources"]["media-receipt.json"] = sha(media_path)
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "decoded original pixel hash differs"):
                audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)


if __name__ == "__main__":
    unittest.main()
