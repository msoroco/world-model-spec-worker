"""Check that the zero-frame diagnostic changes only the intended lamp source."""

import json
import sys
import unittest
from enum import IntFlag
from pathlib import Path
from types import SimpleNamespace as NS


HERE = Path(__file__).resolve().parents[1]
SOURCES = HERE / "diagnostic-sources"
sys.path.insert(0, str(HERE))
from zero_signal_stage import apply_stage


class ZeroSignalProbeTests(unittest.TestCase):
    def test_native_lamp_stage_preserves_unrelated_lights(self):
        class Lights(IntFlag):
            LeftBlinker = 32
            RightBlinker = 16
            LowBeam = 1
        ego = NS(state=Lights.LowBeam | Lights.RightBlinker)
        ego.get_light_state = lambda: ego.state
        ego.set_light_state = lambda state: setattr(ego, "state", state)
        self.assertEqual(apply_stage(ego, Lights, 0, 1)["requested_indicator"], "off")
        self.assertEqual(int(ego.state), 1)
        self.assertEqual(apply_stage(ego, Lights, 1, 1)["requested_indicator"], "left")
        self.assertEqual(int(ego.state), 33)
        with self.assertRaisesRegex(ValueError, "Bounded"):
            apply_stage(ego, Lights, 1, 900)

    def test_original_source_triplet_is_isolated_to_departure_lamp(self):
        expected = {
            "lane_history": ("late-lane_history.jsonl", "zero-lane_history.jsonl"),
            "trace": ("late-trace.jsonl", "zero-trace.jsonl"),
            "capture": ("late-capture-evidence.jsonl", "zero-capture-evidence.jsonl"),
        }
        for kind, (baseline, zero) in expected.items():
            with self.subTest(kind=kind):
                before = [json.loads(line) for line in (SOURCES / baseline).read_text().splitlines()]
                after = [json.loads(line) for line in (SOURCES / zero).read_text().splitlines()]
                self.assertEqual(len(before), 900)
                self.assertEqual(len(after), 900)
                differences = [(old, new) for old, new in zip(before, after) if old != new]
                self.assertEqual(len(differences), 1)
                old, new = differences[0]
                self.assertEqual(old.get("original_frame", old.get("frame")), 101)
                self.assertEqual(new.get("original_frame", new.get("frame")), 101)
                if kind == "lane_history":
                    self.assertEqual((old.pop("indicator"), new.pop("indicator")), ("off", "left"))
                elif kind == "trace":
                    self.assertEqual((old.pop("ego_lamp_bits"), new.pop("ego_lamp_bits")), (0, 32))
                else:
                    old_lamp = old["original_observations"]["participants"][0].pop("light_attributes")
                    new_lamp = new["original_observations"]["participants"][0].pop("light_attributes")
                    self.assertEqual(old_lamp, {"light_LeftBlinker": False, "light_RightBlinker": False})
                    self.assertEqual(new_lamp, {"light_LeftBlinker": True, "light_RightBlinker": False})
                self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
