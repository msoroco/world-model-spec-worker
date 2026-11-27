import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from finalize_sources import analyze, SOURCES
from test_source_rows import sources


SCRATCH = Path.cwd() / ".runtime-work" / "c229831-temp"


def write_fixture(root):
    rig, cameras, context = sources()
    for frame, row in enumerate(rig):
        active = 200 <= frame < 240
        row["requested_method"] = "left_upward" if active else "none"
        row["bone_world_xyz_m"].update({
            "crl_shoulder__L": [0.0, 0.0, 1.4],
            "crl_foreArm__L": [0.0, 0.15 if active else 0.04,
                                1.6 if active else 1.3],
            "crl_hand__L": [0.0, 0.3 if active else 0.08,
                            1.9 if active else 1.2],
        })
    context.update({
        "machine_class": "bicycle", "machine_class_source_id": "original-blueprint",
        "rider_mount_source_id": "original-mount", "rider_arm_source_id": "original-bones",
        "camera_calibration_source_id": "original-four-view-calibration",
    })
    for name, value in (("rider_arm.jsonl", rig), ("camera_frames.jsonl", cameras)):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in value))
    (root / "road_context.json").write_text(json.dumps(context) + "\n")
    seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": True,
            "sources": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                        for name in SOURCES}}
    (root / "capture-seal.json").write_text(json.dumps(seal) + "\n")


class TestSavedFinalizer(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        write_fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_two_measured_methods_and_no_legal_claim(self):
        value = analyze(self.root, allow_fixture=True)
        self.assertEqual(value["right_horizontal"]["right_arm_horizontal_rightward_runs"][0]["first_frame"], 100)
        self.assertEqual(value["left_upward"]["left_arm_upward_frames"], list(range(200, 240)))
        self.assertIsNone(value["legal_conclusion"])
        self.assertFalse(value["original_pixels_verified"])

    def test_rejects_stale_seal_and_missing_capture_source(self):
        camera = self.root / "camera_frames.jsonl"
        camera.write_text(camera.read_text().replace("overview.mkv#frame=100", "different-overview-100"))
        with self.assertRaisesRegex(ValueError, "stale sealed source"):
            analyze(self.root, allow_fixture=True)
        camera.unlink()
        with self.assertRaisesRegex(ValueError, "stale sealed source"):
            analyze(self.root, allow_fixture=True)

    def test_rejects_fixture_as_original(self):
        with self.assertRaisesRegex(ValueError, "Fixture/original mode"):
            analyze(self.root)


if __name__ == "__main__":
    unittest.main()
