import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reverse_alternatives import analyze


def write_case(root, alternative, *, body_centers, headings):
    context = {"alternative": alternative, "native_map_id": "native-signed-site",
               "geometry_source": "authored road mesh and original cameras",
               "camera_source": "original overview and reference-corner frames",
               "road_topology_source": "authored connected-road topology",
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


if __name__ == "__main__":
    unittest.main()
