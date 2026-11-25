"""Original-source contract fixtures; all temporary files stay outside work/."""
import json
from pathlib import Path
import tempfile
import unittest

from finalize import original_measurement
from native_scene import CAMERAS, FRAMES, geometry, request

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / ".runtime-work"


def _fixture(folder, condition="condition_a"):
    folder = Path(folder)
    layout = geometry(condition)
    bicycle = bool(layout["bicycle"])
    context = {"source_kind": "original_native_map_readback",
               "lanes": {name: [] for name in
                         (("roadway", "bicycle", "shoulder", "sidewalk") if bicycle else
                          ("roadway", "shoulder", "sidewalk"))},
               "obstruction_actors": [{"native_actor_id": index} for index in
                                      range(15 if layout["intervening_area_requested_impassable"] else 10)],
               "legal_highway_status_review_pending": True,
               "bike_lane_designation": "native_biking_lane" if bicycle else "absent",
               "road_direction": layout["road_direction"],
               "walking_direction_requested": layout["walking_direction"],
               "intervening_area_requested_impassable": layout["intervening_area_requested_impassable"]}
    (folder / "config.json").write_text(json.dumps({"case_suffix": condition}))
    (folder / "sidewalk_context.json").write_text(json.dumps(context))
    with (folder / "pedestrian-original.jsonl").open("w") as people, \
            (folder / "video_frames.jsonl").open("w") as mapping, \
            (folder / "camera-sources.jsonl").open("w") as cameras:
        for index in range(FRAMES):
            request_row = request(condition, index)
            x, y = request_row["target_xy_m"]
            feet = [[round(x + dx, 6), round(y + dy, 6)]
                    for dx, dy in ((-.16, -.16), (-.16, .16), (.16, -.16), (.16, .16))]
            person = {"video_frame": index, "native_frame": index + 100,
                      "time_s": index / 20, "center_xy_m": [x, y],
                      "footprint_xy_m": feet, "original_native_observed": True}
            hashes = {name: f"rgb-{name}-{index}" for name, *_ in CAMERAS}
            frame = {"video_frame": index, "native_frame": index + 100,
                     "time_s": index / 20, "source_rgb_sha256": hashes}
            people.write(json.dumps(person) + "\n")
            mapping.write(json.dumps(frame) + "\n")
            for name, width, height, *_ in CAMERAS:
                cameras.write(json.dumps({"camera": name, "video_frame": index,
                    "native_frame": index + 100, "time_s": index / 20,
                    "width": width, "height": height,
                    "source_path": name + ".mkv",
                    "source_rgb_sha256": hashes[name]}) + "\n")


class OriginalSourceTests(unittest.TestCase):
    def test_both_native_source_shapes(self):
        SCRATCH.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            for condition in ("condition_a", "condition_b", "direction_east",
                              "direction_west", "bike_passable", "bike_impassable"):
                folder = Path(temporary) / condition
                folder.mkdir()
                _fixture(folder, condition)
                measured = original_measurement(folder)
                self.assertEqual(measured["frames"], 600)
                self.assertLess(measured["first_road_footprint_frame"],
                                measured["first_full_sidewalk_return_frame"])
                self.assertTrue(measured["first_practicable_return_review_pending"])

    def test_missing_original_source_rejected(self):
        SCRATCH.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            folder = Path(temporary)
            _fixture(folder)
            (folder / "sidewalk_context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                original_measurement(folder)

    def test_changed_camera_join_rejected(self):
        SCRATCH.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            folder = Path(temporary)
            _fixture(folder)
            camera = folder / "camera-sources.jsonl"
            rows = camera.read_text().splitlines()
            first = json.loads(rows[0])
            first["native_frame"] += 1
            rows[0] = json.dumps(first)
            camera.write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(ValueError, "join differs"):
                original_measurement(folder)

    def test_missing_return_rejected(self):
        SCRATCH.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            folder = Path(temporary)
            _fixture(folder)
            source = folder / "pedestrian-original.jsonl"
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            for row in rows[370:]:
                row["center_xy_m"][1] = -3.82
                row["footprint_xy_m"] = [[x, -3.82 + dy]
                                          for x, dy in ((row["center_xy_m"][0] - .16, -.16),
                                                        (row["center_xy_m"][0] - .16, .16),
                                                        (row["center_xy_m"][0] + .16, -.16),
                                                        (row["center_xy_m"][0] + .16, .16))]
            source.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            with self.assertRaisesRegex(ValueError, "no original road entry|No original road entry"):
                original_measurement(folder)


if __name__ == "__main__":
    unittest.main()
