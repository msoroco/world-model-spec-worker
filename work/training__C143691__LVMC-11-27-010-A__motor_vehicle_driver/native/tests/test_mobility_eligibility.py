import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mobility_eligibility import audit


class MobilitySourceAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = {
            'device_design': {'source_kind': 'original_native', 'subject_actor_id': 17,
                              'device_class': 'motorized_wheelchair',
                              'designed_for_mobility_impaired_person': True,
                              'blueprint_id': 'vehicle.wheelchair.source_review_pending'},
            'impaired_person_use': {'source_kind': 'original_native', 'subject_actor_id': 17,
                                    'mobility_impaired_person': True, 'device_in_use': True,
                                    'person_id': 'person-17'},
            'operator_binding': {'source_kind': 'original_native', 'subject_actor_id': 17,
                                 'person_id': 'person-17', 'operating_device': True,
                                 'blueprint_id': 'vehicle.wheelchair.source_review_pending'},
        }
        self.packet = {'source_kind': 'original_native', 'subject_actor_id': 17,
                       'frozen_actor': 'motor_vehicle_driver', 'records': {}}
        self.rewrite()

    def rewrite(self):
        for name, value in self.records.items():
            path = self.root / (name + '.json')
            path.write_text(json.dumps(value) + '\n')
            self.packet['records'][name] = {
                'path': path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_bound_sources_preserve_unreviewed_limits(self):
        result = audit(self.root, self.packet)
        self.assertTrue(result['source_bound'])
        self.assertFalse(result['actor_eligibility_reviewed'])
        self.assertFalse(result['legal_outcome_claimed'])

    def test_rejects_conventional_vehicle_relabel(self):
        self.records['device_design']['device_class'] = 'ordinary_motor_vehicle'
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'class not established'):
            audit(self.root, self.packet)

    def test_rejects_missing_design_and_use_independently(self):
        self.records['device_design']['designed_for_mobility_impaired_person'] = False
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'design evidence absent'):
            audit(self.root, self.packet)
        self.records['device_design']['designed_for_mobility_impaired_person'] = True
        self.records['impaired_person_use']['device_in_use'] = False
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'use evidence absent'):
            audit(self.root, self.packet)

    def test_rejects_operator_and_actor_mismatch(self):
        self.records['operator_binding']['person_id'] = 'someone-else'
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'operator binding absent'):
            audit(self.root, self.packet)
        self.records['operator_binding']['person_id'] = 'person-17'
        self.records['operator_binding']['subject_actor_id'] = 18
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'different subject actors'):
            audit(self.root, self.packet)

    def test_rejects_missing_stale_and_nonoriginal_sources(self):
        (self.root / 'device_design.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing original mobility source'):
            audit(self.root, self.packet)
        self.rewrite()
        self.packet['records']['device_design']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit(self.root, self.packet)
        self.rewrite()
        self.records['operator_binding']['source_kind'] = 'synthetic_cpu'
        self.rewrite()
        with self.assertRaisesRegex(ValueError, 'Non-original mobility record'):
            audit(self.root, self.packet)


if __name__ == '__main__':
    unittest.main()
