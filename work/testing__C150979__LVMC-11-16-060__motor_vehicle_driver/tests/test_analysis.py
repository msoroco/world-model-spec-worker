import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analysis
import speed_delivery as speed
from test_speed_delivery import packet


def write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class SavedMeasurementTest(unittest.TestCase):
    def setup_attempt(self, root):
        case = speed.ASSIGNMENT + "__same25_at"
        write(root, "config.json", {"assignment_id": speed.ASSIGNMENT, "selected_case_id": case})
        write(root, "construction.json", {"case_id": case,
            "recording_description": {"channels": [{"name": name, "unit": "structured"}
                for name in ("observed_speed_mph", "governing_posting_context",
                             "original_ego_speed", "original_route_station",
                             "original_sign_inventory", "original_four_camera_pixels")]}})
        site = packet("same25")
        site_ref = write(root, "site.json", site)
        frames = []
        stations = (0, 20, 40, 50, 60, 70, 80, 90, 100)
        for i, station in enumerate(stations):
            row = {"frame_index": i, "source_frame_id": 101 + i,
                   "time_s": i / 20, "ego_alive": True,
                   "driver_role": "motor_vehicle_driver", "map_sha256": site["map_sha256"],
                   "route_station_m": station, "speed_mps": 25 * speed.MPH_TO_MPS}
            if station >= 40:
                row.update(sign_id="S1", sign_value_mph=25)
            frames.append(row)
        history_ref = write(root, "history.json", frames)
        mapping = [{"frame_index": i, "native_frame": 101 + i, "time_s": i / 20}
                   for i in range(9)]
        mapping_ref = write(root, "frame-map.json", mapping)
        write(root, "inventory.json", {"case_id": case, "source_kind": "original_native",
            "frame_count": 9, "camera_views": list(analysis.VIEWS),
            "sources": {"site": site_ref, "history": history_ref, "frame_map": mapping_ref}})
        write(root, "fixture-provenance.json", {"diagnostic_fixture": True})
        (root / "trace.jsonl").write_text("".join(json.dumps({"time_s": i / 20}) + "\n"
                                                    for i in range(9)))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n"
                                                           for row in mapping))

    def test_fixture_source_bound_measurement_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.setup_attempt(root)
            result = analysis.analyze(root, root / "report.json")
            self.assertEqual(result["measurements"]["observed_speed"]["value"]["original_frame_count"], 9)
            (root / "history.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: history.json"):
                analysis.measure(root)
