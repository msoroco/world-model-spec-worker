import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ending_road_device import (DeviceSourceRecorder, devices_at_junction,
                                select_ending_approach_device)


class Waypoint:
    def __init__(self, x, road, lane, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.transform = NS(location=NS(x=x, y=0.))
        self.successors = []

    def next(self, step):
        return self.successors

    def get_junction(self):
        return NS(id=42) if self.is_junction else None


class Light:
    def __init__(self, ident, waypoint, signal='sig-7'):
        self.id, self.waypoint, self.signal = ident, waypoint, signal

    def get_opendrive_id(self):
        return self.signal

    def get_affected_lane_waypoints(self):
        return [self.waypoint]

    def get_state(self):
        return 'TrafficLightState.Red'


class DeviceTests(unittest.TestCase):
    def test_governing_lane_and_original_state_join(self):
        approach = Waypoint(0, 1, -1)
        governed = Waypoint(1, 1, -1)
        junction = Waypoint(3, 2, -1, True)
        governed.successors = [junction]
        light = Light(8, governed)
        selected = select_ending_approach_device([light], [approach, junction], 42)
        self.assertEqual(devices_at_junction([light], 42), [light])
        self.assertEqual(devices_at_junction([light], 43), [])
        with tempfile.TemporaryDirectory() as directory:
            recorder = DeviceSourceRecorder(directory, selected, 42)
            recorder.append(100, 0.)
            recorder.append(101, .05)
            recorder.close()
            context = json.loads((Path(directory) / 'official_device_context.json').read_text())
            self.assertEqual(context['opendrive_signal_id'], 'sig-7')
            self.assertIsNone(context['subsection_4_applicability'])
            self.assertEqual(len((Path(directory) / 'official_device_states.jsonl').read_text().splitlines()), 2)
            with self.assertRaisesRegex(FileExistsError, 'Retain prior'):
                DeviceSourceRecorder(directory, selected, 42)

    def test_rejects_wrong_lane_junction_and_ambiguity(self):
        approach = Waypoint(0, 1, -1)
        junction = Waypoint(3, 2, -1, True)
        wrong_lane = Waypoint(1, 1, -2)
        wrong_lane.successors = [junction]
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            select_ending_approach_device([Light(8, wrong_lane)], [approach, junction], 42)
        governed = Waypoint(1, 1, -1)
        governed.successors = [junction]
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            select_ending_approach_device([Light(8, governed), Light(9, governed)],
                                          [approach, junction], 42)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            select_ending_approach_device([Light(8, governed)], [approach, junction], 43)
