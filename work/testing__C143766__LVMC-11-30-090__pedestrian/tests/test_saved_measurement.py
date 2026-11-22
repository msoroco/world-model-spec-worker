import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_corridor_diagnostics import body
from corridor_construction import make_scene
from saved_measurement import measure_saved
from corridor_map import map_bytes


class SavedMeasurementTests(unittest.TestCase):
    def make_sources(self, directory):
        root = Path(directory)
        scene = make_scene("exact-case", "roadway")
        scene_path = root / "scene.json"
        scene_path.write_text(json.dumps(scene) + "\n")
        frames = [{"case_id": scene["case_id"], "frame": i,
                   "body_xy_m": body(2+i*13, 1.5)} for i in range(3)]
        body_path = root / "body-history.jsonl"
        body_path.write_text("".join(json.dumps(frame)+"\n" for frame in frames))
        map_path = root / "candidate-corridor.xodr"
        map_path.write_bytes(map_bytes())
        manifest = {"format": "c143766-original-pedestrian-sources-v1",
                    "scene": {"path": scene_path.name, "sha256": hashlib.sha256(scene_path.read_bytes()).hexdigest()},
                    "map": {"path": map_path.name, "sha256": hashlib.sha256(map_path.read_bytes()).hexdigest()},
                    "body_history": {"path": body_path.name, "sha256": hashlib.sha256(body_path.read_bytes()).hexdigest()}}
        manifest_path = root / "source-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path, body_path

    def test_positive_and_tampered_original_rejected(self):
        with TemporaryDirectory() as directory:
            manifest, body_path = self.make_sources(directory)
            result = measure_saved(directory, manifest)
            self.assertEqual(result["measurement"]["band_overlap_frame_counts"]["roadway"], 3)
            self.assertTrue(result["original_source_verified"])
            body_path.write_text(body_path.read_text().replace("1.25", "5.25"))
            with self.assertRaisesRegex(ValueError, "hash differs"):
                measure_saved(directory, manifest)

    def test_missing_original_and_case_identity_rejected(self):
        with TemporaryDirectory() as directory:
            manifest, body_path = self.make_sources(directory)
            body_path.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                measure_saved(directory, manifest)
            manifest, body_path = self.make_sources(directory)
            text = body_path.read_text().replace('"exact-case"', '"other-case"')
            body_path.write_text(text)
            data = json.loads(manifest.read_text())
            data["body_history"]["sha256"] = hashlib.sha256(body_path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "case identity differs"):
                measure_saved(directory, manifest)


if __name__ == "__main__":
    unittest.main()
