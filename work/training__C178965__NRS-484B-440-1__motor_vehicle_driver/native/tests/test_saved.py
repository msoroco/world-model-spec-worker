import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


SAVED = Path(__file__).resolve().parents[1] / "finalize_saved.py"
if not SAVED.is_file():
    SAVED = Path(__file__).resolve().parents[2] / "finalize_saved.py"
spec = importlib.util.spec_from_file_location("c178965_saved", SAVED)
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)


def write_lines(path, rows):
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))


def fixture(path, mode):
    y = 5.0 if mode == 1 else 2.8
    survey = {"source_kind": "synthetic_native_sample", "public_highway_reviewed": True,
              "district": "outside", "pavement_left_y_m": -3.5, "pavement_right_y_m": 3.5,
              "pavement_edge_source_id": "synthetic-edge", "offroad_area_source_id": "synthetic-shoulder",
              "visibility_source_id": "synthetic-rays", "disabled_failure_source_id": "synthetic-injection",
              "approach_visibility_sources": {
                  direction: {"source_id": direction + "-synthetic", "path_distance_m": 60.96}
                  for direction in ("forward", "backward")}}
    (path / "original-highway-survey.json").write_text(json.dumps(survey) + "\n")
    trace, visibility, frames = [], [], []
    for i in range(600):
        common = {"frame": i, "native_frame": 1000 + i, "t_s": i / 20}
        trace.append(dict(common, source_kind="synthetic_native_sample", vehicle_id="ego",
                          other_vehicle_id="other", speed_mps=0.0 if 200 <= i < 400 else 4.0,
                          y_m=y, bbox_half_width_m=0.9, failure_active=mode == 3 and 200 <= i < 400))
        visibility.append(dict(common, source_kind="synthetic_native_sample", approaches={
            direction: {"source_id": direction + "-synthetic", "path_distance_m": 60.96,
                        "ray_clear": [True] * 9} for direction in ("forward", "backward")}))
        frames.append({"video_frame": i, "native_frame": 1000 + i, "time_s": i / 20})
    write_lines(path / "roadside-native.jsonl", trace)
    write_lines(path / "visibility-native.jsonl", visibility)
    write_lines(path / "video_frames.jsonl", frames)


class SavedSourceTest(unittest.TestCase):
    def test_all_three_original_shapes_and_measured_difference(self):
        root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        root.mkdir(parents=True, exist_ok=True)
        for mode in (1, 2, 3):
            with tempfile.TemporaryDirectory(dir=root) as directory:
                path = Path(directory)
                fixture(path, mode)
                result = saved.summarize(path, saved.ASSIGNMENT + f"__probe_0{mode}", diagnostic=True)
                self.assertEqual(len(result["stopped"]), 200)
                self.assertIsNone(result["legal_result"])
                self.assertEqual(result["stopped"][0]["pavement_overlap_m"] == 0, mode == 1)
                self.assertEqual(result["stopped"][0]["failure_active"], mode == 3)
                self.assertTrue(result["stopped"][0]["clear_200ft_forward_proxy"])

    def test_missing_backward_rays_rejected(self):
        root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory)
            fixture(path, 2)
            rows = saved.read_json_lines(path / "visibility-native.jsonl")
            del rows[250]["approaches"]["backward"]
            write_lines(path / "visibility-native.jsonl", rows)
            with self.assertRaisesRegex(ValueError, "both directional visibility rays required"):
                saved.summarize(path, saved.ASSIGNMENT + "__probe_02", diagnostic=True)


if __name__ == "__main__":
    unittest.main()
