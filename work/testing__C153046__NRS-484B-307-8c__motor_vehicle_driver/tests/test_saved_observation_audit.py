"""Original-frame replay positives and source/claim tamper negatives."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import AID
from native_observation import from_frame, plan
from saved_observation_audit import audit, sha
from tests.test_native_observation import body, observation_packet


def protocol(root: Path):
    site = observation_packet(root)
    suffix = "stopped_leftmost_clear"
    case_id = AID + "__" + suffix
    scene, source_plan = plan(site, suffix)
    rows = []
    for number in range(2):
        frame = {"origin": "native_world_snapshot", "frame": number,
                 "time_s": number * 0.05, "ego": body(-1.75, -5),
                 "signal_actor_id": "9", "signal_state": "Red",
                 "pedestrians": [body(3, 0)] if number else [],
                 "other_traffic": [body(5, 0)] if number else []}
        observed = from_frame(frame, scene, source_plan)
        rows.append({"case_id": case_id, "source_packet_sha256": sha(site),
                     "selected_approach_lane_id": scene["selected_approach_lane_id"],
                     "original_sample_claim": True, "frame": number,
                     "native_frame": frame,
                     "time_s": observed.time_s,
                     "distance_to_stop_boundary_m": observed.distance_to_stop_boundary_m,
                     "speed_m_s": observed.speed_m_s,
                     "signal": observed.signal,
                     "pedestrian_conflict": observed.pedestrian_conflict,
                     "traffic_conflict": observed.traffic_conflict,
                     "junction_exited": observed.junction_exited})
    trace = root / "trace.jsonl"
    trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return site, trace, case_id, rows


class SavedObservationAuditTests(unittest.TestCase):
    def test_replays_original_body_and_zone_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            site, trace, case_id, _ = protocol(Path(temp))
            receipt = audit(site, trace, case_id, expected_frames=2)
            self.assertEqual(receipt["observation_counts"]["pedestrian_conflict"], 1)
            self.assertEqual(receipt["observation_counts"]["traffic_conflict"], 1)
            self.assertFalse(receipt["physical_acceptance_claimed"])

    def test_rejects_false_claims_even_with_original_participant(self):
        with tempfile.TemporaryDirectory() as temp:
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["pedestrian_conflict"] = False
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "pedestrian_conflict"):
                audit(site, trace, case_id, expected_frames=2)
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["native_frame"]["pedestrians"][0]["body_vertices_xyz_m"] = (
                body(20, 20)["body_vertices_xyz_m"])
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "pedestrian_conflict"):
                audit(site, trace, case_id, expected_frames=2)
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["distance_to_stop_boundary_m"] += 1
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "distance_to_stop_boundary_m"):
                audit(site, trace, case_id, expected_frames=2)
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["native_frame"]["signal_actor_id"] = "different"
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "signal actor differs"):
                audit(site, trace, case_id, expected_frames=2)

    def test_rejects_source_and_frame_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["frame"] = 5
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "outer frame ID"):
                audit(site, trace, case_id, expected_frames=2)
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["source_packet_sha256"] = "0" * 64
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "source or case join"):
                audit(site, trace, case_id, expected_frames=2)
            site, trace, case_id, rows = protocol(Path(temp))
            rows[1]["native_frame"]["frame"] = 3
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "frame/time sequence"):
                audit(site, trace, case_id, expected_frames=2)


if __name__ == "__main__":
    unittest.main()
