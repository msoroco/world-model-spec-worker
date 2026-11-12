import json
from pathlib import Path
import sys
import tempfile
import unittest

OWNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OWNER))

from qualitative_release_audit import audit


class QualitativeReleaseAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.roots = []
        source = json.loads((OWNER / "diagnostic-yield-sweep-0000.json").read_text())["files"]
        rows = [json.loads(line) for line in source["intersection_participants.jsonl"].splitlines()]
        bodies = [row["subject_corners"] for row in rows]
        for rank, delay in enumerate((0, 80, 160)):
            root = Path(self.temp.name) / str(rank)
            root.mkdir()
            for name in ("intersection_topology.json", "intersection_participants.jsonl"):
                (root / name).write_text(source[name])
            config = {
                "selected_case_id": "heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__yield_release_delay-" + f"{rank:04d}",
                "release_delay_frames": delay,
            }
            (root / "config.json").write_text(json.dumps(config))
            shifted = [dict(row, subject_corners=bodies[max(0, i - rank)]) for i, row in enumerate(rows)]
            (root / "intersection_participants.jsonl").write_text("".join(json.dumps(row) + "\n" for row in shifted))
            self.roots.append(root)

    def test_constructed_originals_prove_three_observed_points(self):
        result = audit(self.roots)
        self.assertEqual([point["setpoint_frames"] for point in result["points"]], [0, 80, 160])
        self.assertEqual(len({point["subject_entry_frame"] for point in result["points"]}), 3)
        self.assertFalse(result["legal_threshold_claimed"])

    def test_rejects_repeated_observation_despite_distinct_setpoints(self):
        source = (self.roots[0] / "intersection_participants.jsonl").read_bytes()
        for root in self.roots[1:]:
            (root / "intersection_participants.jsonl").write_bytes(source)
        with self.assertRaisesRegex(ValueError, "lacks measured entry-timing contrast"):
            audit(self.roots)

    def test_rejects_changed_through_vehicle(self):
        path = self.roots[1] / "intersection_participants.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[2]["other_corners"][0][0] += 0.5
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "changed fixed actors"):
            audit(self.roots)


if __name__ == "__main__":
    unittest.main()
