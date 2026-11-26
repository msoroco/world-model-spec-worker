import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reviewed_rail import SOURCE_KINDS, load_reviewed_scene


AID = 'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make(root, suffix='left_99ft'):
    case = AID + '__' + suffix
    map_text = '<OpenDRIVE><road id="rail-site"/></OpenDRIVE>'
    map_sha = sha(map_text.encode())
    fields = {
        'highway': {'public_highway': True, 'one_way_highway': suffix.startswith('one_way'),
                    'centerline_present': True, 'centerline_point_xy': [0, 0],
                    'centerline_heading_xy': [1, 0]},
        'railroad': {'stationary_rail_carrier_person_or_property': True,
                     'streetcar_rail': False},
        'crossing': {'at_grade': True, 'crossing_near_station_m': 0,
                     'crossing_far_station_m': 5, 'route_xy': [[-60, 0], [10, 0]]},
        'vehicle': {'ordinary_motor_vehicle': True, 'driver_actual_control': True},
    }
    sources = {}
    for kind in SOURCE_KINDS:
        record = {'source_kind': kind, 'case_id': case,
                  'map_opendrive_sha256': map_sha,
                  'source_citation': 'test:' + kind, **fields[kind]}
        path = root / (kind + '.json')
        path.write_text(json.dumps(record))
        sources[kind] = {'path': path.name, 'sha256': sha(path.read_bytes()),
                         'reviewer': 'fixture reviewer', 'source_citation': 'test:' + kind}
    packet = root / 'packet.json'
    packet.write_text(json.dumps({'case_id': case, 'law_id': 'NRS-484B-213-2b',
                                  'reviewer': 'fixture reviewer',
                                  'source_citation': 'test:packet',
                                  'map_opendrive_sha256': map_sha,
                                  'sources': sources}))
    return packet, map_text, case


class ReviewedRailTests(unittest.TestCase):
    def test_all_exact_cases_and_source_binding(self):
        for suffix in ('left_101ft', 'left_100ft', 'left_99ft', 'right_99ft',
                       'left_traversal', 'one_way_left_99ft'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                packet, map_text, case = make(root, suffix)
                scene = load_reviewed_scene(packet, root, map_text, case)
                self.assertEqual(scene['reviewed_source_sha256']['crossing'],
                                 sha((root / 'crossing.json').read_bytes()))
                self.assertEqual(scene['one_way_highway'], suffix.startswith('one_way'))

    def test_rejects_map_hash_and_missing_qualification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet, map_text, case = make(root)
            with self.assertRaisesRegex(ValueError, 'live map hash mismatch'):
                load_reviewed_scene(packet, root, '<different/>', case)
            rail = root / 'railroad.json'
            data = json.loads(rail.read_text())
            data['streetcar_rail'] = True
            rail.write_text(json.dumps(data))
            p = json.loads(packet.read_text())
            p['sources']['railroad']['sha256'] = sha(rail.read_bytes())
            packet.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError, 'qualifying railroad unsupported'):
                load_reviewed_scene(packet, root, map_text, case)

    def test_rejects_stale_and_unsafe_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet, map_text, case = make(root)
            (root / 'highway.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_reviewed_scene(packet, root, map_text, case)
            p = json.loads(packet.read_text())
            p['sources']['highway']['path'] = '../highway.json'
            packet.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError, 'unsafe reviewed source path'):
                load_reviewed_scene(packet, root, map_text, case)


if __name__ == '__main__':
    unittest.main()
