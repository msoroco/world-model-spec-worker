"""CPU diagnostics for exact original-source beam measurements."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from beam_measure import LEGAL_DISTANCE_M, measure


REPO = Path(__file__).resolve().parents[2]
TEMP_ROOT = REPO / ".runtime-work" / "c230259-tests"


def fixture(root: Path, count: int = 9) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    site = {"format": "beam-road-site-v1", "source_reviewed": True,
            "nevada_highway_public_access_reviewed": True,
            "lighting_time_source_reviewed": True, "lighting_time_qualifies": True,
            "lamp_mounts_reviewed": True, "driver_eye_sources_reviewed": True,
            "contour_and_load_reviewed": True,
            "source_refs": [{"path": "reviewed-original-map-and-clock", "sha256": "a" * 64}]}
    (root / "site-packet.json").write_text(json.dumps(site) + "\n")
    states, maps = [], []
    for i in range(count):
        frame = 1732 + i
        state = {"frame": frame, "time_s": 87 + i / 20, "actors": {
            "ego": {"id": 1, "center_m": [0, 0, 0], "driver_eye_m": [0, 0, 1.4],
                    "speed_mps": 2, "body_radius_m": 2, "lamp_command_bits": 4,
                    "lamp_state_bits": 4, "on_traveled_highway_or_adjacent_shoulder": True},
            "oncoming": {"id": 2, "center_m": [154 - i, 0, 0],
                           "driver_eye_m": [154 - i, 0, 1.4], "speed_mps": 2,
                           "body_radius_m": 2, "opposing_route": True},
            "person": {"id": 3, "center_m": [45, 1, 0]},
            "target_vehicle": {"id": 4, "center_m": [70, 1, 0]}}}
        states.append(state)
        maps.append({"frame": frame, **{view + "_source_frame": frame for view in
                                       ("overview", "approach", "reference_corner", "driver_reference")}})
    for name, rows in (("actor-state.jsonl", states), ("camera-frame-map.jsonl", maps)):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")}


class BeamMeasureTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="beam-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hashes = fixture(self.root)

    def test_original_joins_and_both_distance_endpoints(self):
        result = measure(self.root, self.hashes, expected_frames=9)
        self.assertEqual(result["frame_count"], 9)
        self.assertEqual(result["actor_ids"], {"ego": 1, "oncoming": 2, "person": 3, "target_vehicle": 4})
        self.assertAlmostEqual(result["legal_distance_m"], 152.4)
        self.assertTrue(result["rows"][0]["body_gap_within_500_ft"])
        self.assertFalse(result["rows"][0]["eye_gap_within_500_ft"])
        self.assertEqual(result["rows"][-1]["lamp_state_bits"], 4)

    def test_stale_original_hash_is_rejected(self):
        (self.root / "actor-state.jsonl").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "changed original source"):
            measure(self.root, self.hashes, expected_frames=9)

    def test_unreviewed_qualifying_time_is_rejected(self):
        path = self.root / "site-packet.json"
        site = json.loads(path.read_text())
        site["lighting_time_source_reviewed"] = False
        path.write_text(json.dumps(site) + "\n")
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "reviewed qualifying"):
            measure(self.root, hashes, expected_frames=9)

    def test_missing_participant_is_rejected(self):
        path = self.root / "actor-state.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        del rows[3]["actors"]["person"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "all original participant"):
            measure(self.root, hashes, expected_frames=9)

    def test_stale_camera_frame_is_rejected(self):
        path = self.root / "camera-frame-map.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[5]["approach_source_frame"] -= 1
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "synchronized original camera"):
            measure(self.root, hashes, expected_frames=9)

    def test_non_opposing_route_is_rejected(self):
        path = self.root / "actor-state.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["actors"]["oncoming"]["opposing_route"] = False
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "oncoming route"):
            measure(self.root, hashes, expected_frames=9)


if __name__ == "__main__":
    unittest.main()
