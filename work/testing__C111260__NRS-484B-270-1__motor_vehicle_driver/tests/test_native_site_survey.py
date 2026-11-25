import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from bicycle_encounter import SourceError, verify_site
from native_site_survey import survey, verify_packet

ASSIGNMENT = 'testing__C111260__NRS-484B-270-1__motor_vehicle_driver'


class Carla:
    @staticmethod
    def Location(**values):
        return SimpleNamespace(**values)


class Map:
    name = 'TownNative'
    def __init__(self, offset=0.0, junction=True):
        self.offset = offset
        self.junction = junction
    def to_opendrive(self):
        return '<OpenDRIVE>original loaded map</OpenDRIVE>'
    def get_waypoint(self, location, project_to_road):
        assert project_to_road is True
        return SimpleNamespace(transform=SimpleNamespace(location=SimpleNamespace(
            x=location.x+self.offset, y=location.y)), road_id=12, lane_id=-1,
            is_junction=self.junction)


class World:
    def __init__(self, map_obj):
        self.map_obj = map_obj
    def get_map(self):
        return self.map_obj


def request():
    return {'assignment_id': ASSIGNMENT, 'cell_id': 'C111260', 'layout': 'intersection',
            'maneuver': 'travel', 'control': 'cyclist',
            'ego_route_xy': [[-10, 0], [10, 0]], 'rider_route_xy': [[0, -10], [0, 10]]}


class SurveyTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_source_bound_native_survey(self):
        result = survey(World(Map()), Carla, request(), self.root)
        self.assertEqual(result['crossings_xy'], [[0.0, 0.0]])
        packet = verify_packet(self.root, result['original_sources'][1])
        self.assertEqual(packet['waypoint_readbacks']['ego'][0]['road_id'], 12)
        self.assertEqual(packet['native_map_name'], 'TownNative')
        self.assertIsNone(packet['legal_verdict'])
        self.assertEqual(len(result['original_sources']), 2)

    def test_survey_consumed_by_encounter_constructor(self):
        result = survey(World(Map()), Carla, request(), self.root)
        device = {'human_powered': True, 'tandem_wheels': 2,
                  'one_wheel_diameter_in': 26, 'moped': False,
                  'observed_blueprint_id': 'vehicle.bh.crossbike',
                  'rendered_person_present': True}
        classification = {'blueprint_id': 'vehicle.bh.crossbike', 'classification': device}
        rules = {'jurisdiction': 'Nevada', 'applicable_rules': ['NRS 484B.270(1)']}
        import hashlib
        refs = list(result['original_sources'])
        for name, value in [('bicycle.json', classification), ('rules.json', rules)]:
            path = self.root / name
            path.write_text(json.dumps(value), encoding='utf-8')
            refs.append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        identity = {'reviewer': 'fixture-reviewer', 'assignment_id': ASSIGNMENT,
                    'cell_id': 'C111260'}
        conduct_path = self.root / 'conduct.json'
        conduct_path.write_text('{"observed_signal":"green"}', encoding='utf-8')
        conduct_ref = {'path': conduct_path.name,
                       'sha256': hashlib.sha256(conduct_path.read_bytes()).hexdigest()}
        refs.append(conduct_ref)
        observations = {'device': device,
                        'rider': {'distinct_from_ego': True, 'person_visible_in_review': True},
                        'rules': {**rules, 'conduct_sources': [conduct_ref]}}
        review_refs = {}
        for role, data in observations.items():
            asset_path = self.root / (role + '-asset.json')
            asset_path.write_text(json.dumps({'original_fixture_role': role}), encoding='utf-8')
            asset_ref = {'path': asset_path.name,
                         'sha256': hashlib.sha256(asset_path.read_bytes()).hexdigest()}
            refs.append(asset_ref)
            path = self.root / (role + '-review.json')
            path.write_text(json.dumps({**identity, 'observations': data,
                                        'original_asset': asset_ref}), encoding='utf-8')
            review_refs[role + '_review'] = {'path': path.name,
                                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            refs.append(review_refs[role + '_review'])
        inventory = {**identity, 'rider_kind': 'human_powered_bicycle',
                     'blueprint_id': classification['blueprint_id'],
                     'lawful_riding_verdict': None, 'intent_verdict': None,
                     'interference_verdict': None, 'device_observations': device,
                     'rider_observations': observations['rider'],
                     'rules_observations': observations['rules'],
                     'original_sources': review_refs}
        inventory_path = self.root / 'inventory.json'
        inventory_path.write_text(json.dumps(inventory), encoding='utf-8')
        refs.append({'path': inventory_path.name,
                     'sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest()})
        site = {**request(), 'native_map_name': result['native_map_name'],
                'original_sources': refs, 'map_source_path': result['map_source_path'],
                'bicycle_classification_source_path': 'bicycle.json',
                'rider_rules_source_path': 'rules.json', 'jurisdiction': 'Nevada',
                'rider_inventory_source_path': 'inventory.json',
                'rider_kind': 'human_powered_bicycle',
                'ego_blueprint_id': 'vehicle.tesla.model3',
                'bicycle_blueprint_id': classification['blueprint_id'],
                'bicycle_classification': classification['classification'],
                'ego_actor_id': 'ego', 'rider_actor_id': 'rider'}
        self.assertEqual(verify_site(site, self.root), [(0.0, 0.0)])
        packet_path = self.root / result['map_source_path']
        packet = json.loads(packet_path.read_text())
        packet['waypoint_readbacks']['ego'][0]['native_waypoint_xy'] = [3, 3]
        packet_path.write_text(json.dumps(packet), encoding='utf-8')
        site['original_sources'][1]['sha256'] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(SourceError, 'waypoint readback mismatch'):
            verify_site(site, self.root)

    def test_original_map_and_packet_tamper(self):
        result = survey(World(Map()), Carla, request(), self.root)
        (self.root / 'native-map.xodr').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(SourceError, 'OpenDRIVE hash mismatch'):
            verify_packet(self.root, result['original_sources'][1])
        result = survey(World(Map()), Carla, request(), self.root)
        packet_path = self.root / 'native-route-survey.json'
        packet = json.loads(packet_path.read_text())
        packet['crossings_xy'] = [[100, 100]]
        packet_path.write_text(json.dumps(packet), encoding='utf-8')
        with self.assertRaisesRegex(SourceError, 'survey packet hash mismatch'):
            verify_packet(self.root, result['original_sources'][1])

    def test_bad_geometry_and_waypoint_rejected(self):
        bad = request()
        bad['rider_route_xy'] = [[12, -10], [12, 10]]
        with self.assertRaisesRegex(SourceError, 'never intersect'):
            survey(World(Map()), Carla, bad, self.root)
        with self.assertRaisesRegex(SourceError, 'snap exceeds'):
            survey(World(Map(offset=2.1)), Carla, request(), self.root)
        with self.assertRaisesRegex(SourceError, 'intersection waypoint'):
            survey(World(Map(junction=False)), Carla, request(), self.root)

    def test_catalog_and_identity_rejected(self):
        bad = request()
        bad['assignment_id'] = 'other'
        with self.assertRaisesRegex(SourceError, 'assignment/cell'):
            survey(World(Map()), Carla, bad, self.root)


if __name__ == '__main__':
    unittest.main()
