import json
from pathlib import Path
import unittest

from parking_scene import check


class ExactParkingRequest(unittest.TestCase):
    def test_exact_request(self):
        request=json.loads(Path('request.json').read_text())
        self.assertTrue(check(request)['passed'])
        self.assertFalse(request['authority_request']['original_authority_verified'])

    def test_one_way_geometry(self):
        request=json.loads(Path('request.json').read_text())
        self.assertEqual(request['roadway_lanes']['same_direction_driving'],[-1,-2])
        self.assertEqual(request['frames'],600)


if __name__=='__main__':unittest.main()
