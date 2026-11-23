"""Synthetic byte-custody and geometry checks for a proposed Native site."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_bound_scene import build, sha


def fixture(root: Path) -> dict:
    names = ("opendrive", "signal_authority", "approach_lanes",
             "receiving_lanes", "stop_boundary")
    sources = {}
    for name in names:
        path = root / (name + ".txt")
        path.write_text("synthetic CPU site protocol: " + name + "\n")
        sources[name] = {"path": path.name, "sha256": sha(path),
                         "citation": "synthetic protocol fixture", "reviewer": "CPU test"}
    return {"format": "c153046-reviewed-site-proposal", "reviewer": "CPU protocol only",
            "sources": sources,
            "approach": {"one_way": True, "direction_xy": [0, 1],
                         "reference_xy": [0, 0],
                         "lane_centers_xy": {"west": [-1.75, 0], "east": [1.75, 0]},
                         "extreme_left_lane_id": "west"},
            "receiving": {"one_way_to_left": True, "direction_xy": [-1, 0]},
            "signal": {"native_actor_id": "protocol-signal",
                       "phase_source": "original_frame_history"},
            "stop_boundary": {"hierarchy_reviewed": True, "point_xy": [0, -2]}}


class SourceBoundSceneTests(unittest.TestCase):
    def test_exact_lane_and_receiving_direction_probes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            baseline = build(path, "stopped_leftmost_clear")
            self.assertEqual(baseline["selected_approach_lane_id"], "west")
            self.assertEqual(baseline["stop_boundary_progress_m"], -2)
            self.assertFalse(baseline["physical_realization_claimed"])
            inner = build(path, "stopped_inner_lane_clear")
            self.assertEqual(inner["selected_approach_lane_id"], "east")
            packet["receiving"]["one_way_to_left"] = False
            path.write_text(json.dumps(packet))
            two_way = build(path, "stopped_leftmost_two_way_receive")
            self.assertEqual(two_way["receiving_direction_request"], "two_way")
            with self.assertRaisesRegex(ValueError, "one-way, official signal"):
                build(path, "stopped_leftmost_clear")

    def test_changed_source_and_wrong_left_lane_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            (root / "opendrive.txt").write_text("changed synthetic road\n")
            with self.assertRaisesRegex(ValueError, "retained source missing or changed"):
                build(path, "stopped_leftmost_clear")
            packet["sources"]["opendrive"]["sha256"] = sha(root / "opendrive.txt")
            packet["approach"]["extreme_left_lane_id"] = "east"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "extreme-left lane differs"):
                build(path, "stopped_leftmost_clear")
            packet["approach"]["extreme_left_lane_id"] = "west"
            packet["receiving"]["direction_xy"] = [1, 0]
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "do not form a left turn"):
                build(path, "stopped_leftmost_clear")


if __name__ == "__main__":
    unittest.main()
