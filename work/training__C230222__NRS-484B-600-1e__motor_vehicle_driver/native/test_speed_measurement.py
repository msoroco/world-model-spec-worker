"""Positive and adversarial CPU diagnostics for the saved speed source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import speed_measurement as meter


class SpeedMeasurementTest(unittest.TestCase):
    def measure(self, raw: bytes, digest: str | None = None) -> dict:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "native_samples.jsonl"
            path.write_bytes(raw)
            return meter.measure(path, digest or hashlib.sha256(raw).hexdigest())

    def test_three_boundary_settings(self):
        relations = {78: "measured_not_above_80_mph",
                     80: "unresolved_at_80_mph",
                     82: "measured_above_80_mph"}
        for requested, relation in relations.items():
            with self.subTest(requested=requested):
                result = self.measure(meter.synthetic_fixture(requested))
                self.assertEqual(result["measured_relation"], relation)
                self.assertAlmostEqual(result["peak_speed_mph"], requested, places=4)
                self.assertEqual(result["frames"], 600)
                self.assertEqual(result["source_kind"], "synthetic_native_sample")
                self.assertIsNone(result["legal_verdict"])

    def test_changed_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.measure(meter.synthetic_fixture(82), hashlib.sha256(b"stale").hexdigest())

    def test_missing_frame_rejected(self):
        raw = b"\n".join(meter.synthetic_fixture(82).splitlines()[:-1]) + b"\n"
        with self.assertRaisesRegex(ValueError, "600 complete"):
            self.measure(raw)

    def test_changed_actor_rejected(self):
        rows = [json.loads(line) for line in meter.synthetic_fixture(82).splitlines()]
        rows[100]["ego_actor_id"] = 202
        with self.assertRaisesRegex(ValueError, "Subject or source kind changed"):
            self.measure(self.serialize(rows))

    def test_pose_velocity_disagreement_rejected(self):
        rows = [json.loads(line) for line in meter.synthetic_fixture(82).splitlines()]
        rows[100]["ego_velocity_mps"] = [0, 0, 0]
        with self.assertRaisesRegex(ValueError, "pose and velocity disagree"):
            self.measure(self.serialize(rows))

    def test_nonfinite_velocity_rejected(self):
        rows = [json.loads(line) for line in meter.synthetic_fixture(82).splitlines()]
        rows[100]["ego_velocity_mps"][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "Invalid velocity component"):
            self.measure(self.serialize(rows))

    def test_timestamp_and_identity_rejected(self):
        rows = [json.loads(line) for line in meter.synthetic_fixture(82).splitlines()]
        rows[100]["time_s"] += .01
        with self.assertRaisesRegex(ValueError, "timestamp"):
            self.measure(self.serialize(rows))
        rows[100]["time_s"] -= .01
        rows[100]["cell_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.measure(self.serialize(rows))

    @staticmethod
    def serialize(rows: list[dict]) -> bytes:
        return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


if __name__ == "__main__":
    unittest.main(verbosity=2)
