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
        short_rows = [json.loads(line) for line in source["intersection_participants.jsonl"].splitlines()]
        for rank, delay in enumerate((0, 80, 160)):
            root = Path(self.temp.name) / str(rank)
            root.mkdir()
            (root / "intersection_topology.json").write_text(source["intersection_topology.json"])
            config = {
                "selected_case_id": "heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__yield_release_delay-" + f"{rank:04d}",
                "release_delay_frames": delay,
                "frames": 320,
            }
            (root / "config.json").write_text(json.dumps(config))
            rows, mapping, trace = [], [], []
            for i in range(320):
                # All three runs retain the same through actor; only the subject
                # release changes, with enough original frames for 160 ticks.
                subject_index = min(8, max(0, i - delay))
                row = dict(short_rows[min(i, 8)], frame=38033 + i,
                           time_s=(i + 1) * .05,
                           subject_corners=short_rows[subject_index]["subject_corners"])
                rows.append(row)
                mapping.append({"video_frame": i, "carla_frame": row["frame"],
                                "time_s": row["time_s"]})
                trace.append({"frame": row["frame"], "time_s": row["time_s"]})
            for name, values in (("intersection_participants.jsonl", rows),
                                 ("video_frames.jsonl", mapping), ("trace.jsonl", trace)):
                (root / name).write_text("".join(json.dumps(value) + "\n" for value in values))
            self.roots.append(root)

    def test_constructed_originals_prove_three_observed_points(self):
        result = audit(self.roots)
        self.assertEqual([point["setpoint_frames"] for point in result["points"]], [0, 80, 160])
        self.assertEqual(len({point["subject_entry_frame"] for point in result["points"]}), 3)
        self.assertEqual([point["subject_entry_frame"] - result["points"][0]["subject_entry_frame"]
                          for point in result["points"]], [0, 80, 160])
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

    def test_rejects_short_or_unjoined_originals(self):
        root = self.roots[1]
        path = root / "video_frames.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n")
        with self.assertRaisesRegex(ValueError, "frame-map or trace length"):
            audit(self.roots)
        path.write_text("\n".join(lines) + "\n")
        participant = root / "intersection_participants.jsonl"
        participant.write_text("\n".join(participant.read_text().splitlines()[:9]) + "\n")
        with self.assertRaisesRegex(ValueError, "does not span"):
            audit(self.roots)


if __name__ == "__main__":
    unittest.main()
