import hashlib
import json
from pathlib import Path
import unittest
from runner import check
from candidates import construction
from geometry import requested_tracks, native_track_requests

class OfficialConstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_request_and_preflight(self):
        case, candidate = self.config['case_suffix'], self.config['candidate_id']
        plan = construction(case, candidate)
        self.assertTrue(check(case, candidate)['passed'])
        self.assertEqual(check(case, candidate)['native_track_rows'], 480)
        self.assertEqual(check(case, candidate)['camera_count'], 4)
        self.assertFalse(check(case, candidate)['carla_imported'])
        rows = native_track_requests(case, **plan['knobs'])
        source = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
        self.assertEqual(hashlib.sha256(source).hexdigest(), self.config['native_requests_sha256'])
        self.assertTrue(all(r['approach_role_request'] == 'official_vehicle_of_regulatory_agency'
                            and r['lamp_request']['qualification_unverified'] for r in rows))
        self.assertFalse(self.config['vehicle_authority_verified'])

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            check('unrelated', self.config['candidate_id'])

if __name__ == '__main__':
    unittest.main()
