"""Focused CPU checks of source requirements and both thirty-minute boundaries."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_timing import HASH_FIELDS, derive


def packet(local_datetime="2026-04-15T15:30:00-07:00"):
    result = {
        "source_kind": "original_school_schedule_and_device_readback",
        "local_datetime": local_datetime,
        "last_operation_end": "2026-04-15T15:00:00-07:00",
        "next_operation_start": "2026-04-16T08:00:00-07:00",
        "class_start": "2026-04-15T08:00:00-07:00",
        "class_end": "2026-04-15T15:00:00-07:00",
        "school_in_session": True,
        "beacon_operational": True,
        "zone_designated_by_operational_beacon": True,
        "beacon_yellow_light_count": 2,
        "beacon_alternating_flash_capable": True,
        "sign_limit_active": True,
        "lamp_state_samples": [
            {"original_frame": i, "yellow_lamps_on": [i % 2 == 0, i % 2 == 1]}
            for i in range(4)
        ],
    }
    result.update({name: str(i + 1).zfill(64) for i, name in enumerate(HASH_FIELDS)})
    return result


class TimingTests(unittest.TestCase):
    def test_after_end_boundary_triple(self):
        actual = [derive(packet(f"2026-04-15T15:{minute:02d}:00-07:00")) for minute in (29, 30, 31)]
        self.assertEqual([x["after_end_minutes"] for x in actual], [29, 30, 31])
        self.assertEqual([x["half_hour_boundary"] for x in actual], [False, True, False])
        self.assertEqual([x["between_operation_interior"] for x in actual], [False, False, True])
        self.assertTrue(all(x["legal_judgment"] is None for x in actual))

    def test_before_start_boundary_triple(self):
        actual = [derive(packet(f"2026-04-16T07:{minute:02d}:00-07:00")) for minute in (29, 30, 31)]
        self.assertEqual([x["before_start_minutes"] for x in actual], [31, 30, 29])
        self.assertEqual([x["half_hour_boundary"] for x in actual], [False, True, False])
        self.assertEqual([x["between_operation_interior"] for x in actual], [True, False, False])

    def test_missing_independent_source_rejected(self):
        sample = packet()
        del sample["calendar_source_sha256"]
        with self.assertRaisesRegex(ValueError, "calendar_source_sha256"):
            derive(sample)

    def test_beacon_definition_requires_two_alternating_lamps(self):
        sample = packet()
        sample["beacon_yellow_light_count"] = 1
        sample["lamp_state_samples"] = [
            {"original_frame": i, "yellow_lamps_on": [i % 2 == 0]} for i in range(4)
        ]
        with self.assertRaisesRegex(ValueError, "beacon definition"):
            derive(sample)
        sample = packet()
        sample["lamp_state_samples"] = [
            {"original_frame": i, "yellow_lamps_on": [False, False]} for i in range(4)
        ]
        self.assertFalse(derive(sample)["alternating_flash_observed"])

    def test_sign_only_requires_explicit_governance(self):
        sample = packet()
        sample["zone_designated_by_operational_beacon"] = False
        sample["beacon_operational"] = False
        self.assertFalse(derive(sample)["zone_designated_by_operational_beacon"])
        bad = copy.deepcopy(sample)
        bad["zone_designated_by_operational_beacon"] = True
        with self.assertRaisesRegex(ValueError, "beacon definition"):
            derive(bad)

    def test_naive_clock_rejected(self):
        sample = packet()
        sample["local_datetime"] = "2026-04-15T15:30:00"
        with self.assertRaisesRegex(ValueError, "offset-aware"):
            derive(sample)


if __name__ == "__main__":
    unittest.main()
