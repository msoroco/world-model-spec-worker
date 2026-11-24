import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('assigned_saved_measurement', ROOT / 'saved_measurement.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SCENE = ROOT / 'scenes' / 'destination_occupied_absent.json'


def packet():
    return {'source': 'original_native_map', 'map_name': 'SourceTown',
            'intersection_id': 'I-17',
            'highway_context': {'source': 'original_map_and_local_review'},
            'crosswalk': {'source': 'original_map_marking',
                          'polygon_xy_m': [[-2,-1],[2,-1],[2,5],[-2,5]]},
            'ego_turn': {'direction': 'left', 'connected': True,
                         'waypoints': [[-8,-4],[-2,-2],[0,0],[0,8]],
                         'destination_lane_ids': ['north_1', 'north_2']},
            'lanes': [{'lane_id':'north_1','direction':'north','type':'driving',
                       'polygon_xy_m':[[-2,0],[0,0],[0,9],[-2,9]]},
                      {'lane_id':'north_2','direction':'north','type':'driving',
                       'polygon_xy_m':[[0,0],[2,0],[2,9],[0,9]]},
                      {'lane_id':'south_1','direction':'south','type':'driving',
                       'polygon_xy_m':[[2,0],[4,0],[4,9],[2,9]]}],
            'official_devices': {'inventory_source':'original_map_and_actor_scan',
                                 'coverage':'all_relevant_approaches','entries':[]}}


def fixture(root):
    scene = json.loads(SCENE.read_text())
    data = {
        'site': packet(),
        'ego': [{'frame':i, 'elapsed_s':i/20, 'actor_id':101,
                 'classification':'motor_vehicle_driver','body_center_xy_m':[0,-2],
                 'brake':True} for i in range(600)],
        'pedestrian': [{'frame':i, 'elapsed_s':i/20, 'actor_id':202,
                        'classification':'pedestrian','body_center_xy_m':[1,2]}
                       for i in range(600)],
        'exception_review': {'case_id':scene['case_id'], 'status':'none_identified',
                             'source_refs':['review/exception-source.json']},
    }
    index = {'format':'c111610-native-source-index-v1','case_id':scene['case_id'],
             'scene_sha256':hashlib.sha256(SCENE.read_bytes()).hexdigest(),
             'map_name':'SourceTown','files':{}}
    for name, value in data.items():
        path = root / (name + '.json')
        path.write_text(json.dumps(value) + '\n')
        index['files'][name] = {'path':path.name,
                                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                'source':'native_original'}
    (root/'source-index.json').write_text(json.dumps(index) + '\n')
    return data, index


def write_data(root, data, index, name):
    path = root / (name + '.json')
    path.write_text(json.dumps(data[name]) + '\n')
    index['files'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root/'source-index.json').write_text(json.dumps(index) + '\n')


class SavedMeasurementTests(unittest.TestCase):
    def test_600_original_frames_and_sealed_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            fixture(root)
            result = m.process(root, SCENE, root/'out.json')
            self.assertEqual(result['frame_count'], 600)
            self.assertEqual(result['summary']['crosswalk_and_destination_half_frames'], 600)
            self.assertEqual(result['summary']['ego_brake_frames'], 600)
            self.assertTrue(result['summary']['planned_device_condition_matches'])
            self.assertEqual(result['legal_judgment'], 'unresolved')
            self.assertFalse(result['physical_source_verified'])

    def test_tamper_and_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            fixture(root)
            (root/'pedestrian.json').write_text('[]')
            with self.assertRaisesRegex(m.SavedSourceError, 'hash mismatch'):
                m.process(root, SCENE, root/'out.json')
            (root/'pedestrian.json').unlink()
            with self.assertRaisesRegex(m.SavedSourceError, 'missing'):
                m.process(root, SCENE, root/'out.json')

    def test_frame_time_and_identity_drift_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            data, index = fixture(root)
            data['ego'][25]['elapsed_s'] = 99
            write_data(root, data, index, 'ego')
            with self.assertRaisesRegex(m.SavedSourceError, 'time mismatch'):
                m.process(root, SCENE, root/'out.json')
            data['ego'][25]['elapsed_s'] = 25/20
            data['ego'][25]['actor_id'] = 999
            write_data(root, data, index, 'ego')
            with self.assertRaisesRegex(m.SavedSourceError, 'identity drift'):
                m.process(root, SCENE, root/'out.json')

    def test_scene_and_provenance_drift_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            _, index = fixture(root)
            index['scene_sha256'] = '0'*64
            (root/'source-index.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(m.SavedSourceError, 'construction hash'):
                m.process(root, SCENE, root/'out.json')
            index['scene_sha256'] = hashlib.sha256(SCENE.read_bytes()).hexdigest()
            index['files']['site']['source'] = 'fixture'
            (root/'source-index.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(m.SavedSourceError, 'provenance'):
                m.process(root, SCENE, root/'out.json')

    def test_source_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            _, index = fixture(root)
            index['files']['site']['path'] = '../site.json'
            (root/'source-index.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(m.SavedSourceError, 'outside attempt'):
                m.process(root, SCENE, root/'out.json')

    def test_unverified_device_state_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            data, index = fixture(root)
            data['site']['official_devices']['entries'] = [{
                'official':True,'relevant':True,'source_ref':'native/signal.jsonl',
                'state_by_frame':{'0':'operating'}}]
            write_data(root, data, index, 'site')
            with self.assertRaisesRegex(Exception, 'state missing'):
                m.process(root, SCENE, root/'out.json')


if __name__ == '__main__':
    unittest.main()
