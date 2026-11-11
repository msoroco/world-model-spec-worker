from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aggressive_window_measurement import measure


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = [{'frame': 100 + i, 'time_s': i * .05,
                       'x_m': i * 2.0, 'y_m': 0.0} for i in range(5)]
        self.events = []

    def event(self, frame, category, identity, **extra):
        self.events.append({'frame': frame, 'category': category,
                            'occurrence_id': identity, 'source_ref': 'driving_trace.jsonl',
                            **extra})

    def write(self):
        raw = ''.join(json.dumps(row) + '\n' for row in self.trace)
        (self.root / 'driving_trace.jsonl').write_text(raw)
        digest = sha256(raw.encode()).hexdigest()
        for event in self.events:
            event.setdefault('source_sha256', digest)
        (self.root / 'event_annotations.json').write_text(json.dumps(self.events))

    def result(self):
        return measure(self.root / 'driving_trace.jsonl',
                       self.root / 'event_annotations.json', self.root)

    def test_repeated_act_and_one_frame_hazard_candidate(self):
        self.event(100, 'speed', 's')
        self.event(101, 'device', 'd1')
        self.event(102, 'device', 'd2')
        self.event(103, 'hazard', 'h', target_type='person')
        self.write()
        result = self.result()
        window = result['candidate_window']
        self.assertEqual((window['start_frame'], window['end_frame']), (100, 103))
        self.assertEqual(window['path_m'], 6)
        self.assertTrue(window['repeated_predicate_category'])
        self.assertEqual(window['hazard_target_types'], ['person'])
        self.assertIsNone(result['aggressive_driving_legal_judgment'])

    def test_different_acts_and_missing_element(self):
        self.event(100, 'speed', 's')
        self.event(101, 'marked_lane', 'a')
        self.event(102, 'yield', 'b')
        self.event(103, 'hazard', 'h', target_type='vehicle')
        self.write()
        self.assertFalse(self.result()['candidate_window']['repeated_predicate_category'])
        self.events.pop(2)
        self.write()
        self.assertIsNone(self.result()['candidate_window'])

    def test_one_mile_span_and_source_rejection(self):
        self.trace[-1]['x_m'] = 1800
        self.event(100, 'speed', 's')
        self.event(101, 'device', 'd1')
        self.event(102, 'device', 'd2')
        self.event(104, 'hazard', 'h', target_type='person')
        self.write()
        self.assertIsNone(self.result()['candidate_window'])
        self.events[-1]['source_sha256'] = '0' * 64
        self.write()
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            self.result()

    def test_discontinuous_trace_and_invalid_hazard_target(self):
        self.event(100, 'hazard', 'h', target_type='object')
        self.write()
        with self.assertRaisesRegex(ValueError, 'Hazard target'):
            self.result()
        self.events[0]['target_type'] = 'person'
        self.trace[2]['frame'] = 999
        self.write()
        with self.assertRaisesRegex(ValueError, 'not continuous'):
            self.result()


if __name__ == '__main__':
    unittest.main()
