import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("night_parking_measurement", ROOT / "night_parking_measurement.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def utc(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


class NightParkingMeasurementTests(unittest.TestCase):
    def test_duration_and_window_boundaries(self):
        self.assertEqual(MODULE.night_overlap_seconds(utc("2026-11-27T10:00:00Z"), utc("2026-11-27T10:30:01Z"), "America/Los_Angeles"), 1801)
        self.assertEqual(MODULE.night_overlap_seconds(utc("2026-11-27T08:10:00Z"), utc("2026-11-27T08:40:01Z"), "America/Los_Angeles"), 0)
        self.assertEqual(MODULE.night_overlap_seconds(utc("2026-11-27T08:59:59Z"), utc("2026-11-27T09:00:01Z"), "America/Los_Angeles"), 1)
        self.assertEqual(MODULE.night_overlap_seconds(utc("2026-11-27T13:59:59Z"), utc("2026-11-27T14:00:01Z"), "America/Los_Angeles"), 1)

    def _fixture(self, root):
        body = [[0, 0], [1, 0], [1, 1], [0, 1]]
        frames = []
        start = utc("2026-11-27T10:00:00Z")
        for i in range(21):
            frames.append({"frame": 400 + i, "utc_time": (start + dt.timedelta(seconds=i / 20)).isoformat(),
                           "subject": {"body_vertices_xy_m": body, "on_street": True, "parked": True, "speed_m_s": 0.0},
                           "other_vehicle": {"body_vertices_xy_m": body}})
        files = {
            "context": {"iana_timezone": "America/Los_Angeles", "municipal_jurisdiction_source": "survey", "street_source": "map"},
            "classification": {"transport_capable": True, "self_propelled": False, "vehicle_exclusions_checked": True, "physical_source": "build inventory"},
            "activity": {"responsible_person_source": "operator record", "activity_source": "original event", "episode_start_event_source": "original event", "episode_end_event_source": "original event", "start_frame": 400, "end_frame": 420, "activity": "parking"},
        }
        contract = {"sources": {}}
        for name, value in files.items():
            path = root / (name + ".json")
            path.write_text(json.dumps(value) + "\n")
            contract["sources"][name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        path = root / "trace.jsonl"
        path.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
        contract["sources"]["trace"] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        frame_map = root / "video_frames.jsonl"
        frame_map.write_text("".join(json.dumps({"carla_frame": frame["frame"], "video_frame": i, "time_s": i / 20}) + "\n" for i, frame in enumerate(frames)))
        contract["sources"]["frame_map"] = {"path": frame_map.name, "sha256": hashlib.sha256(frame_map.read_bytes()).hexdigest()}
        return contract, frames

    def test_source_join_and_negative_paths(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            contract, frames = self._fixture(root)
            result = MODULE.measure(root, contract)
            self.assertEqual(result["frame_count"], 21)
            self.assertEqual(result["elapsed_s"], 1)
            self.assertIsNone(result["legal_conclusion"])
            trace = root / "trace.jsonl"
            trace.write_text(trace.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                MODULE.measure(root, contract)
            trace.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
            contract["sources"]["trace"]["sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
            activity = root / "activity.json"
            original_activity = json.loads(activity.read_text())
            changed_activity = dict(original_activity, start_frame=401)
            activity.write_text(json.dumps(changed_activity) + "\n")
            contract["sources"]["activity"]["sha256"] = hashlib.sha256(activity.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "event/frame join"):
                MODULE.measure(root, contract)
            activity.write_text(json.dumps(original_activity) + "\n")
            contract["sources"]["activity"]["sha256"] = hashlib.sha256(activity.read_bytes()).hexdigest()
            trace.write_text("".join(json.dumps(frame) + "\n" for frame in frames[:8] + frames[9:]))
            contract["sources"]["trace"]["sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "trace/frame count mismatch"):
                MODULE.measure(root, contract)
            trace.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
            contract["sources"]["trace"]["sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
            frame_map = root / "video_frames.jsonl"
            rows = [json.loads(line) for line in frame_map.read_text().splitlines()]
            rows[3]["video_frame"] = 20
            frame_map.write_text("".join(json.dumps(row) + "\n" for row in rows))
            contract["sources"]["frame_map"]["sha256"] = hashlib.sha256(frame_map.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "video/frame/time join"):
                MODULE.measure(root, contract)

    def test_fixed_capture_window_with_shorter_internal_parking_episode(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            contract, frames = self._fixture(root)
            for frame in frames[:2] + frames[-2:]:
                frame["subject"]["parked"] = False
            trace = root / "trace.jsonl"
            trace.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
            contract["sources"]["trace"]["sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
            activity = root / "activity.json"
            event = json.loads(activity.read_text())
            event.update(start_frame=402, end_frame=418)
            activity.write_text(json.dumps(event) + "\n")
            contract["sources"]["activity"]["sha256"] = hashlib.sha256(activity.read_bytes()).hexdigest()
            measured = MODULE.measure(root, contract)
            self.assertEqual(measured["frame_count"], 21)
            self.assertEqual(measured["parked_frame_count"], 17)
            self.assertAlmostEqual(measured["elapsed_s"], .8)


if __name__ == "__main__":
    unittest.main()
