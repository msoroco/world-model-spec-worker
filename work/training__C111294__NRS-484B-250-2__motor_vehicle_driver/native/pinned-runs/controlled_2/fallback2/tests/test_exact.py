import json
import sys
import tempfile
import unittest
from pathlib import Path

root = Path.cwd()
native = root / "work" / "training__C111294__NRS-484B-250-2__motor_vehicle_driver" / "native"
sys.path.insert(0, str(native))
from check import check
from saved import make_raw, process

class ExactCrossroads(unittest.TestCase):
    def setUp(self):
        self.bundle = native / "drafts" / "controlled_2" / "fallback2"

    def test_source_bound_request(self):
        result = check(self.bundle)
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["delivery_ready"])

    def test_synthetic_saved_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            raw.write_text(json.dumps(make_raw(self.bundle)))
            saved = process(self.bundle, raw)
            self.assertEqual(saved["frames_joined"], 600)
            self.assertFalse(saved["original_native_observed"])

    def test_rehashed_track_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            for original in self.bundle.iterdir():
                (bundle / original.name).write_bytes(original.read_bytes())
            track = bundle / "requested-tracks.jsonl"
            rows = [json.loads(line) for line in track.read_text().splitlines()]
            rows[1]["requested_other_xyz_m"][1] += 0.25
            track.write_text("".join(json.dumps(row) + "\n" for row in rows))
            cfg = json.loads((bundle / "config.json").read_text())
            import hashlib
            cfg["tracks_sha256"] = hashlib.sha256(track.read_bytes()).hexdigest()
            (bundle / "config.json").write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                check(bundle)
