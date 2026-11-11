import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from turn_context import analyze


class TurnContextTests(unittest.TestCase):
    def _sources(self, root):
        route_context = {"intersection_id": 7, "routes": {
            "ego": [[-10, 0], [-4, 0], [0, 0], [10, 0]],
            "other": [[0, -10], [0, -4], [0, 0], [0, 10]]}}
        geometry = {"intersection_id": 7, "ego_approach_heading_deg": 0, "other_approach_heading_deg": 90}
        (root / "turn_route_context.json").write_text(json.dumps(route_context))
        (root / "road_geometry.json").write_text(json.dumps(geometry))
        rows = [{"frame": 100+i, "time_s": i*.05,
                 "ego": {"heading_deg": 0, "native_road_id": 1, "native_lane_id": -1},
                 "other": {"heading_deg": 90, "native_road_id": 2, "native_lane_id": -1}}
                for i in range(2)]
        frames = [{"carla_frame": 100+i, "time_s": i*.05, "video_frame": i}
                  for i in range(2)]
        (root / "crossing_history.jsonl").write_text("".join(json.dumps(x)+"\n" for x in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(x)+"\n" for x in frames))
        return route_context

    def test_source_bound_routes_and_original_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self._sources(root)
            result = analyze(root)
            self.assertEqual(result["approach_difference_deg"], 90)
            self.assertTrue(result["original_heading_complete"])
            self.assertEqual(result["routes"]["ego"]["route_deflection_deg"], 0)
            self.assertEqual(result["statutory_exception_judgment"], "unresolved")

    def test_mismatched_frame_and_route_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); route_context = self._sources(root)
            frames = [json.loads(x) for x in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(x)+"\n" for x in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                analyze(root)
            self._sources(root)
            route_context["routes"]["other"] = [[0,-10], [0,-4], [0,0], [10,0]]
            (root / "turn_route_context.json").write_text(json.dumps(route_context))
            # Exit shape can change, while the reviewed approach must still match.
            self.assertEqual(analyze(root)["routes"]["other"]["route_deflection_deg"], -90)
            route_context["routes"]["other"] = [[0,-10], [6,-10], [6,-4], [6,4]]
            (root / "turn_route_context.json").write_text(json.dumps(route_context))
            with self.assertRaisesRegex(ValueError, "conflicts with sourced approach"):
                analyze(root)

    def test_saved_result_source_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self._sources(root)
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ("turn_route_context.json", "road_geometry.json", "crossing_history.jsonl", "video_frames.jsonl")}
            (root / "result.json").write_text(json.dumps({"source_evidence_hashes": hashes}))
            self.assertTrue(analyze(root)["original_heading_complete"])
            (root / "road_geometry.json").write_text((root / "road_geometry.json").read_text() + " ")
            with self.assertRaisesRegex(ValueError, "differs from saved result"):
                analyze(root)


if __name__ == "__main__":
    unittest.main()
