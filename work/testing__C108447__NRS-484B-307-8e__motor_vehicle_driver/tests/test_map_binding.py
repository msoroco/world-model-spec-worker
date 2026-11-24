import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('map_binding', BASE / 'map_binding.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MapBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.xodr = root / 'original.xodr'
        self.xodr.write_text('<OpenDRIVE><header name="source"/></OpenDRIVE>\n')
        self.authority = root / 'parcels.json'
        self.parcels = {'format': 'original-parcel-authority-v1',
                        'opendrive_sha256': module._sha(self.xodr), 'map_name': 'source',
                        'coordinate_frame': 'native-map', 'intersecting_street_id': 'B',
                        'properties': [{'id': 'lot', 'status': 'private', 'authority': 'parcel register',
                                        'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
        self.save()
        self.args = {'property_id': 'lot', 'intersecting_street_id': 'B',
                     'connector_routes': {'lot': [[-3, 5], [5, 5], [13, 5]]},
                     'review': {'reviewer': 'source reviewer', 'source': 'parcel register', 'decision': 'reviewed'}}

    def save(self):
        self.authority.write_text(json.dumps(self.parcels) + '\n')

    def test_original_map_and_parcel_seals_join(self):
        packet = module.bind(self.xodr, self.authority, **self.args)
        self.assertEqual(packet['native_map']['sha256'], module._sha(self.xodr))
        self.assertEqual(packet['source']['sha256'], module._sha(self.authority))
        self.assertEqual(packet['properties'][0]['status'], 'private')

    def test_wrong_map_seal_rejected(self):
        self.parcels['opendrive_sha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'map seal differs'):
            module.bind(self.xodr, self.authority, **self.args)

    def test_unreviewed_authority_rejected(self):
        args = dict(self.args)
        args['review'] = {'reviewer': 'source reviewer', 'source': 'parcel register', 'decision': 'pending'}
        with self.assertRaisesRegex(ValueError, 'explicit original authority review'):
            module.bind(self.xodr, self.authority, **args)

    def test_missing_route_or_destination_rejected(self):
        args = dict(self.args)
        args['connector_routes'] = {}
        with self.assertRaisesRegex(ValueError, 'connector route required'):
            module.bind(self.xodr, self.authority, **args)
        args = dict(self.args)
        args['intersecting_street_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'destination street authority differs'):
            module.bind(self.xodr, self.authority, **args)

    def test_duplicate_parcel_and_missing_classification_rejected(self):
        self.parcels['properties'].append(dict(self.parcels['properties'][0]))
        self.save()
        with self.assertRaisesRegex(ValueError, 'distinct source parcel'):
            module.bind(self.xodr, self.authority, **self.args)
        self.parcels['properties'].pop()
        self.parcels['properties'][0]['status'] = 'unknown'
        self.save()
        with self.assertRaisesRegex(ValueError, 'classification and authority'):
            module.bind(self.xodr, self.authority, **self.args)


if __name__ == '__main__':
    unittest.main()
