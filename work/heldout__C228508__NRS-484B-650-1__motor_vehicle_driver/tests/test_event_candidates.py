import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_candidates import derive, write_candidates


def body(x, speed):
    corners = [[x+dx, dy, dz] for dx in (-2, 2)
               for dy in (-1, 1) for dz in (0, 1)]
    return {'position_m': [x, 0, 0], 'yaw_deg': 0,
            'speed_mps': speed, 'body_corners_m': corners}


class CandidateTests(unittest.TestCase):
    def test_source_cited_review_candidates_and_no_speed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'following_sources.jsonl'
            rows = []
            for i, phase in enumerate(('first_closing_request',
                                       'separate_encounters',
                                       'second_closing_request',
                                       'continue_driving')):
                rows.append({'frame': 100+i, 'time_s': i*.05,
                             'ego': body(i*2, 15), 'lead': body(i*2+10, 5),
                             'requested_phase': phase,
                             'map_speed_limit_kmh': 40})
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            events = derive(path)
            self.assertEqual([e['category'] for e in events],
                             ['speed', 'too_close', 'hazard', 'too_close'])
            self.assertTrue(all(e['review_status'].startswith('unreviewed')
                                for e in events))
            self.assertEqual(events[2]['target_type'], 'vehicle')
            destination = root / 'event_annotations.json'
            self.assertEqual(write_candidates(path, destination), events)
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                write_candidates(path, destination)
            for row in rows:
                row['ego']['speed_mps'] = 8
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertNotIn('speed', [e['category'] for e in derive(path)])


if __name__ == '__main__':
    unittest.main()
