import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_instruction import measure

SITE = {
    "stop_line": [[0, -3], [0, 3]],
    "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
    "bike_blueprint_id": "vehicle.bicycle",
    "device_id": "10",
    "police_authority_source": "dispatch-original-sha",
}
CASE = {"case_id": "exact-red-cross", "device_instruction": "red",
        "officer_direction": "none", "operator_motion": "cross_stop_line"}
SITE_SHA = "a" * 64


def packet(case=CASE):
    rows = []
    for i in range(900):
        crossing = case["operator_motion"] == "cross_stop_line"
        x = -10 + 20 * i / 899 if crossing else -10 + 9 * min(i, 100) / 100
        rows.append({
            "frame": 100 + i, "time_s": 5 + i * 0.05,
            "bike_id": "22", "bike_blueprint_id": "vehicle.bicycle",
            "device_id": "10", "device_state": case["device_instruction"],
            "bike_front_xy": [x, 0.0],
            "bike_speed_mps": 3.0 if crossing or i < 100 else 0.0,
            "officer_actor_id": "99" if case["officer_direction"] != "none" else None,
            "officer_authority_source": SITE["police_authority_source"] if case["officer_direction"] != "none" else None,
            "officer_recipient_id": "22" if case["officer_direction"] != "none" else None,
            "officer_command": case["officer_direction"],
        })
    return {"format": "c111329-native-instruction-trace", "source_kind": "original_native",
            "case_id": case["case_id"], "site_sha256": SITE_SHA, "samples": rows}


def run_measure(data, case=CASE, declared_sha=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "original-trace.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return measure(path, declared_sha or actual, case, SITE, SITE_SHA)


class TestSavedInstruction(unittest.TestCase):
    def test_crossing_and_hold_measurements(self):
        crossing = run_measure(packet())
        self.assertEqual(crossing["frame_count"], 900)
        self.assertIsNotNone(crossing["crossing_frame"])
        self.assertEqual(crossing["device_state_at_response"], "red")
        self.assertEqual(crossing["legal_assessment"], "unresolved")
        hold_case = {**CASE, "case_id": "exact-red-hold", "operator_motion": "hold_before_stop_line"}
        hold = run_measure(packet(hold_case), hold_case)
        self.assertIsNone(hold["crossing_frame"])
        self.assertEqual(hold["hold_window_frames"], [980, 999])

    def test_officer_direction_recipient_and_timing(self):
        case = {**CASE, "case_id": "exact-officer-proceed", "officer_direction": "proceed"}
        self.assertEqual(run_measure(packet(case), case)["officer_command_at_response"], "proceed")
        wrong = packet(case)
        wrong["samples"][450]["officer_recipient_id"] = "other"
        with self.assertRaisesRegex(ValueError, "recipient mismatch"):
            run_measure(wrong, case)
        late = packet(case)
        for row in late["samples"][430:451]:
            row["officer_command"] = "none"
        with self.assertRaisesRegex(ValueError, "absent before response"):
            run_measure(late, case)

    def test_source_binding_and_integrity_rejections(self):
        with self.assertRaisesRegex(ValueError, "trace hash mismatch"):
            run_measure(packet(), declared_sha="0" * 64)
        wrong = packet()
        wrong["site_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "site source binding"):
            run_measure(wrong)
        incomplete = packet()
        incomplete["samples"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete original"):
            run_measure(incomplete)
        clock = packet()
        clock["samples"][500]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "clock discontinuity"):
            run_measure(clock)

    def test_response_rejections(self):
        missing = packet()
        for row in missing["samples"]:
            row["bike_front_xy"] = [-1.0, 0.0]
        with self.assertRaisesRegex(ValueError, "crossing absent"):
            run_measure(missing)
        hold_case = {**CASE, "case_id": "exact-hold", "operator_motion": "hold_before_stop_line"}
        moving = packet(hold_case)
        for row in moving["samples"][-20:]:
            row["bike_speed_mps"] = 0.3
        with self.assertRaisesRegex(ValueError, "observable dwell"):
            run_measure(moving, hold_case)
        wrong_state = packet()
        wrong_state["samples"][100]["device_state"] = "green"
        with self.assertRaisesRegex(ValueError, "instruction differs"):
            run_measure(wrong_state)


if __name__ == "__main__":
    unittest.main()
