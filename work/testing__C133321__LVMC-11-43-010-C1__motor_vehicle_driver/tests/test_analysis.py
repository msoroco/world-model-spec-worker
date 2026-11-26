import hashlib
import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("c133321_analysis", HERE / "analysis.py")
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)
from test_roundabout import topology_source, history


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class TestSavedMeasurement(unittest.TestCase):
    def _attempt(self, root):
        case = HERE.name + "__left_lane_u_turn"
        write(root / "config.json", {"assignment_id": HERE.name, "selected_case_id": case})
        write(root / "construction.json", {"case_id": case})
        map_packet = topology_source()
        map_ref = write(root / "map.json", map_packet)
        observed = history("lane-inner", case)
        for index, row in enumerate(observed["frames"]):
            if index < 200:
                x, y = -4.0 + 4.0 * index / 199.0, -2.0
            elif index <= 600:
                angle = -math.pi / 2.0 + math.pi * (index - 200) / 400.0
                x, y = 2.0 * math.cos(angle), 2.0 * math.sin(angle)
            else:
                x, y = -4.0 * (index - 601) / 298.0, 2.0
            row["x"], row["y"] = x, y
        history_ref = write(root / "history.json", observed)
        write(root / "inventory.json", {"case_id": case, "source_kind": "original_native",
                "frame_count": 900, "camera_views": list(ANALYSIS.VIEWS),
                "sources": {"map": map_ref, "history": history_ref}})

    def test_original_lane_and_departure_measured(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            self._attempt(root)
            self.assertTrue(ANALYSIS.measure_lane_use(root)["requested_lane_observed"])
            self.assertTrue(ANALYSIS.measure_opposite_departure(root)["opposite_departure_observed"])

    def test_missing_and_stale_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            self._attempt(root)
            (root / "history.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                ANALYSIS.measure(root)
            (root / "history.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: history.json"):
                ANALYSIS.measure(root)
