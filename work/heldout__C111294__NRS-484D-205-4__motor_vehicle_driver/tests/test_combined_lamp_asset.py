import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combined_lamp_asset import (construct_combined, validate_combined_inventory,
                                 verify_combined_capture)


class CombinedLampAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'asset-inspection.json'
        self.record = {
            'blueprint_id': 'vehicle.example', 'inspection_method': 'asset_mesh_review',
            'inspector': 'synthetic fixture reviewer', 'inspection_status': 'reviewed',
            'installed_backup_lamps': [{'location': 'rear', 'asset_source': 'fixture mesh',
                'housing_id': 'rear-right', 'arrangement': 'combined'}],
            'other_lamps': [{'lamp_function': 'tail', 'asset_source': 'fixture mesh',
                'housing_id': 'rear-right'}]}

    def write(self):
        self.path.write_text(json.dumps(self.record) + '\n')

    def test_shared_housing_and_source_hash(self):
        self.write()
        measured = validate_combined_inventory(self.path, 'vehicle.example')
        self.assertEqual(measured['shared_housing_ids'], ['rear-right'])
        self.assertEqual(measured['installed_backup_lamp_count'], 1)
        self.assertEqual(len(measured['inspection_source_sha256']), 64)
        self.assertFalse(measured['physical_acceptance_claimed'])

    def test_rejects_unreviewed_or_separate_housing(self):
        self.record['inspection_status'] = 'pending'
        self.write()
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            validate_combined_inventory(self.path, 'vehicle.example')
        self.record['inspection_status'] = 'reviewed'
        self.record['other_lamps'][0]['housing_id'] = 'rear-left'
        self.write()
        with self.assertRaisesRegex(ValueError, 'one housing'):
            validate_combined_inventory(self.path, 'vehicle.example')

    def test_multiple_backup_lamps_may_share_one_cited_housing(self):
        self.record['installed_backup_lamps'].append({
            'location': 'rear-left', 'asset_source': 'fixture mesh',
            'housing_id': 'rear-right', 'arrangement': 'combined'})
        self.write()
        measured = validate_combined_inventory(self.path, 'vehicle.example')
        self.assertEqual(measured['installed_backup_lamp_count'], 2)
        packet = dict(self.record, kind='motor_vehicle',
                      arrangement='combined', shared_housing_ids=['rear-right'],
                      combined_inspection_sha256=measured['inspection_source_sha256'])
        source = Path(self.temp.name) / 'equipment.json'
        source.write_text(json.dumps(packet) + '\n')
        self.assertEqual(verify_combined_capture(source, 'vehicle.example')['shared_housing_ids'],
                         ['rear-right'])

    def test_native_construction_called_only_after_asset_check(self):
        self.write()
        config = {'ego_blueprint_id': 'vehicle.example',
                  'installed_backup_lamp_count': 1, 'lamp_arrangement': 'combined'}
        scene = {'equipment': {'blueprint_id': 'vehicle.example',
                               'installed_backup_lamps': self.record['installed_backup_lamps']}}
        with patch('lamp_scene.construct', return_value=scene) as construct:
            result = construct_combined(object(), object(), config, self.path)
            construct.assert_called_once()
        self.assertEqual(result['equipment']['arrangement'], 'combined')
        self.assertEqual(result['equipment']['shared_housing_ids'], ['rear-right'])
        packet = Path(self.temp.name) / 'equipment.json'
        packet.write_text(json.dumps(result['equipment']) + '\n')
        self.assertEqual(verify_combined_capture(packet, 'vehicle.example')['shared_housing_ids'],
                         ['rear-right'])
        result['equipment']['other_lamps'][0]['housing_id'] = 'rear-left'
        packet.write_text(json.dumps(result['equipment']) + '\n')
        with self.assertRaisesRegex(ValueError, 'shared housing differs'):
            verify_combined_capture(packet, 'vehicle.example')
        config['lamp_arrangement'] = 'separate'
        with patch('lamp_scene.construct') as construct:
            with self.assertRaisesRegex(ValueError, 'Exact combined construction'):
                construct_combined(object(), object(), config, self.path)
            construct.assert_not_called()


if __name__ == '__main__':
    unittest.main()
