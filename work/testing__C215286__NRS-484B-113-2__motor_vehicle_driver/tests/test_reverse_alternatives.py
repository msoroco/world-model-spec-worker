import json
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reverse_alternatives import analyze
from reverse_alternative_finalizer import ASSIGNMENT, finalize


def write_case(root, alternative, *, body_centers, headings):
    sources = {}
    for label in ("site_packet_source", "geometry_source", "camera_source", "road_topology_source"):
        path = label + ".txt"
        content = "Synthetic original " + label + "\n"
        (root / path).write_text(content)
        sources[label] = {"path": path,
                          "sha256": hashlib.sha256(content.encode()).hexdigest()}
    context = {"alternative": alternative, "native_map_id": "native-signed-site",
               **sources,
               "intersection_polygon_xy_m": [[-3, -3], [1, -3], [1, 3], [-3, 3]],
               "street_corner_region_xy_m": [[-3, -3], [1, -3], [1, 3], [-3, 3]]}
    (root / "reverse_site_context.json").write_text(json.dumps(context) + "\n")
    history, frames = [], []
    for index, ((x, y), heading) in enumerate(zip(body_centers, headings)):
        fid = 100 + index
        time = round(fid / 20, 2)
        body = [[x - .5, y - .5], [x - .5, y + .5],
                [x + .5, y + .5], [x + .5, y - .5]]
        history.append({"frame": fid, "time_s": time, "native_reverse": True,
                        "heading_deg": heading, "ego_body_vertices_xy_m": body})
        frames.append({"video_frame": index, "carla_frame": fid, "time_s": time})
    (root / "reverse_history.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in history))
    (root / "video_frames.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in frames))


class AlternativeTests(unittest.TestCase):
    def test_intersection_body_entry_requires_backward_motion(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_case(root, "intersection", body_centers=[(4, 0), (2, 0), (0, 0)],
                       headings=[0, 0, 0])
            result = analyze(root, "intersection")
            self.assertTrue(result["reverse_body_enters_region"])
            self.assertTrue(result["samples"][-1]["body_region_overlap_area_m2"] > 0)
            self.assertEqual(result["legal_conclusion"],
                             "unresolved pending original site and camera review")
            write_case(root, "intersection", body_centers=[(4, 0), (5, 0), (6, 0)],
                       headings=[0, 0, 0])
            with self.assertRaisesRegex(ValueError, "No original backward body motion"):
                analyze(root, "intersection")

    def test_corner_reports_heading_change_only_on_original_reverse_samples(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_case(root, "street_corner", body_centers=[(4, 0), (2, 0), (0, 0)],
                       headings=[0, 0, 45])
            result = analyze(root, "street_corner")
            self.assertEqual(result["reverse_heading_change_deg"], 45)
            self.assertEqual(result["heading_change_while_in_corner_deg"], 45)
            frames = root / "video_frames.jsonl"
            frames.write_text(frames.read_text().replace('"carla_frame": 101', '"carla_frame": 999'))
            with self.assertRaisesRegex(ValueError, "frame join differs"):
                analyze(root, "street_corner")

    def test_changed_site_source_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_case(root, "intersection", body_centers=[(4, 0), (2, 0), (0, 0)],
                       headings=[0, 0, 0])
            (root / "geometry_source.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "Changed original site source"):
                analyze(root, "intersection")

    def test_saved_finalizer_uses_original_sources_and_rejects_site_change(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_case(root, "intersection", body_centers=[(4, 0), (2, 0), (0, 0)],
                       headings=[0, 0, 0])
            site = {"alternative": "intersection", "expected_entry": True,
                    "native_map_id": "native-signed-site",
                    "region_polygon_xy_m": [[-3, -3], [1, -3], [1, 3], [-3, 3]]}
            (root / "intersection_site.json").write_text(json.dumps(site) + "\n")
            context = json.loads((root / "reverse_site_context.json").read_text())
            context["expected_entry"] = True
            context["site_packet_source"] = {
                "path": "intersection_site.json",
                "sha256": hashlib.sha256((root / "intersection_site.json").read_bytes()).hexdigest()}
            (root / "reverse_site_context.json").write_text(json.dumps(context) + "\n")
            case = ASSIGNMENT + "__reverse_into_intersection"
            (root / "config.json").write_text(json.dumps({
                "selected_case_id": case,
                "recording_description": {"channels": [{"name": "region_overlap"}]}}) + "\n")
            (root / "trace.jsonl").write_text("{}\n")
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text("{}\n")
            for camera in ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                           "driver_reference.mkv"):
                (root / camera).write_bytes(b"fixture placeholder")
            native = types.ModuleType("worker_exchange.native_output")
            native.physical_result = lambda attempt, result: dict(
                result, physical_checks={"setup": {"status": "unverified"}})
            native.write_result = lambda attempt, result: (
                attempt / "result.json").write_text(json.dumps(result) + "\n")
            package = types.ModuleType("worker_exchange")
            package.__path__ = []
            with patch.dict(sys.modules, {"worker_exchange": package,
                                          "worker_exchange.native_output": native}):
                result = finalize(root, root / "analysis.json")
            self.assertTrue(result["source_report"]["reverse_body_enters_region"])
            self.assertFalse(result["legal_verdict_asserted"])
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_case(root, "intersection", body_centers=[(4, 0), (2, 0), (0, 0)],
                       headings=[0, 0, 0])
            (root / "config.json").write_text(json.dumps({
                "selected_case_id": ASSIGNMENT + "__reverse_into_intersection"}) + "\n")
            (root / "intersection_site.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "Missing required original source"):
                finalize(root, root / "analysis.json")


if __name__ == "__main__":
    unittest.main()
