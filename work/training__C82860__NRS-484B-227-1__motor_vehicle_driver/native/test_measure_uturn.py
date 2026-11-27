"""Saved-only source joins and authority hash rejection for C82860."""

import json
from pathlib import Path
import tempfile
import unittest

from measure_uturn import measure_attempt
from road_request import CAMERAS, request


def square(x, y):
    return [[x - .1, y - .1], [x + .1, y - .1],
            [x + .1, y + .1], [x - .1, y + .1]]


def fixture(folder, case):
    q = request(case)
    (folder / "request.json").write_text(json.dumps(q) + "\n")
    context = {"source_kind": "synthetic_native_sample",
               "median_bounds_m": q["median_bounds_m"],
               "opening_bounds_m": q["opening_bounds_m"],
               "barrier_bounds_m": q["barrier_bounds_m"],
               "authored_road_ids": q["road_ids"],
               "native_roadways": [{"road_id": road_id, "lane_id": -1,
                                    "heading_deg": heading}
                                   for road_id, heading in zip(q["road_ids"], (0, 180))]}
    (folder / "divided-road-context.json").write_text(json.dumps(context) + "\n")
    source = folder / "authority-source.json"
    source.write_text('{"public_authority_establishment":"unassessed"}\n')
    from measure_uturn import digest
    review = {"format": "worker-divided-road-authority-source",
              "source": {"path": source.name, "sha256": digest(source)}}
    (folder / "source-review.json").write_text(json.dumps(review) + "\n")
    x = q["requested_crossing_x_m"]
    names = [name for name, _, _ in CAMERAS]
    with (folder / "native-uturn.jsonl").open("w") as body, \
            (folder / "video_frames.jsonl").open("w") as frames:
        for index in range(600):
            native = index + 30
            y = -6.75 + 13.5 * index / 599
            body.write(json.dumps({"native_frame": native,
                                   "video_frame": index, "time_s": index / 20,
                                   "ego": {"actor_id": 1,
                                           "blueprint_id": "vehicle.tesla.model3",
                                           "body_xy_m": square(x, y),
                                           "yaw_deg": 90}}) + "\n")
            frames.write(json.dumps({"native_frame": native,
                                     "video_frame": index,
                                     "camera_native_frames": {name: native for name in names}}) + "\n")


class SavedUturnTest(unittest.TestCase):
    def setUp(self):
        root = Path.cwd() / ".runtime-work"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_distinct_crossing_measurements_stay_unjudged(self):
        fixture(self.folder, "authorized_opening")
        opening = measure_attempt(self.folder)
        self.assertGreater(opening["opening_overlap_frames"], 0)
        self.assertEqual(opening["median_without_opening_overlap_frames"], 0)
        self.assertFalse(opening["authority_verified"])
        self.assertEqual(opening["legal_judgment"], "unresolved")
        fixture(self.folder, "barrier_crossing")
        barrier = measure_attempt(self.folder)
        self.assertGreater(barrier["median_without_opening_overlap_frames"], 0)
        self.assertEqual(barrier["opening_overlap_frames"], 0)

    def test_missing_source_and_camera_join_rejected(self):
        fixture(self.folder, "authorized_opening")
        (self.folder / "authority-source.json").unlink()
        with self.assertRaisesRegex(ValueError, "authority source hash"):
            measure_attempt(self.folder)
        fixture(self.folder, "authorized_opening")
        path = self.folder / "video_frames.jsonl"
        lines = path.read_text().splitlines()
        bad = json.loads(lines[100])
        bad["camera_native_frames"].pop("overview")
        lines[100] = json.dumps(bad)
        path.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ValueError, "camera frames"):
            measure_attempt(self.folder)


if __name__ == "__main__":
    unittest.main()
