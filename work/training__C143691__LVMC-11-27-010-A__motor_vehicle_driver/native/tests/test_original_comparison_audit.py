import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from original_comparison_audit import audit, original


AID = 'training__C143691__LVMC-11-27-010-A__motor_vehicle_driver'
BASE_REQUEST = {'official_designation': True, 'city_dedication': True,
                'appropriate_posting': True, 'exception_kind': 'none'}


def side(suffix, occupancy=600):
    return {'case_id': AID + '__' + suffix, 'request': dict(BASE_REQUEST),
            'route_case': 'within', 'road_sha256': 'road',
            'camera_plan': [{'name': name} for name in (
                'overview', 'approach', 'reference_corner', 'driver_reference')],
            'occupancy_frames': occupancy, 'blueprint_id': 'vehicle.base',
            'candidate_id': 'primary', 'barrier_clear_gap_m': 3.5,
            'barrier_blueprint_id': 'static.prop.streetbarrier',
            'result_sha256': 'result-' + suffix,
            'delivery_receipt_sha256': 'delivery-' + suffix}


class OriginalComparisonContract(unittest.TestCase):
    def pair(self, name):
        left, right = side('all_present'), side(name)
        if name == 'occupancy':
            left, right = side('outside', 0), side('all_present')
            left['route_case'] = 'outside'
        elif name == 'designation':
            right['case_id'] = AID + '__no_designation'
            right['request']['official_designation'] = False
        elif name == 'dedication':
            right['case_id'] = AID + '__no_dedication'
            right['request']['city_dedication'] = False
        elif name == 'posting':
            right['case_id'] = AID + '__no_posting'
            right['request']['appropriate_posting'] = False
        elif name == 'emergency':
            right['request']['exception_kind'] = 'emergency_vehicle'
            right['blueprint_id'] = 'vehicle.emergency'
        elif name == 'maintenance':
            right['request']['exception_kind'] = 'right_of_way_maintenance'
            right['blueprint_id'] = 'vehicle.utility'
        spec = {'comparison_id': AID + '__' + name,
                'case_ids': [left['case_id'], right['case_id']]}
        return spec, left, right

    def test_all_six_requests(self):
        for name in ('occupancy', 'designation', 'dedication', 'posting',
                     'emergency', 'maintenance'):
            with self.subTest(name=name):
                spec, left, right = self.pair(name)
                receipt = audit(spec, left, right)
                self.assertTrue(receipt['passed'])
                self.assertFalse(receipt['legal_outcome_claimed'])
                left['candidate_id'] = right['candidate_id'] = 'fallback1'
                left['barrier_clear_gap_m'] = right['barrier_clear_gap_m'] = 5.5
                self.assertEqual(audit(spec, left, right)['shared_candidate_id'], 'fallback1')

    def test_rejects_extra_change_and_missing_occupancy(self):
        spec, left, right = self.pair('designation')
        right['request']['appropriate_posting'] = False
        with self.assertRaisesRegex(ValueError, 'unexpected source condition'):
            audit(spec, left, right)
        spec, left, right = self.pair('occupancy')
        right['occupancy_frames'] = 0
        with self.assertRaisesRegex(ValueError, 'distinction absent'):
            audit(spec, left, right)

    def test_rejects_fixed_road_camera_subject(self):
        spec, left, right = self.pair('posting')
        wrong = copy.deepcopy(right)
        wrong['road_sha256'] = 'another-road'
        with self.assertRaisesRegex(ValueError, 'road or camera'):
            audit(spec, left, wrong)
        wrong = copy.deepcopy(right)
        wrong['camera_plan'].pop()
        with self.assertRaisesRegex(ValueError, 'road or camera'):
            audit(spec, left, wrong)
        wrong = copy.deepcopy(right)
        wrong['blueprint_id'] = 'another-vehicle'
        with self.assertRaisesRegex(ValueError, 'subject blueprint'):
            audit(spec, left, wrong)
        wrong = copy.deepcopy(right)
        wrong['candidate_id'] = 'fallback1'
        with self.assertRaisesRegex(ValueError, 'barrier candidate'):
            audit(spec, left, wrong)
        wrong = copy.deepcopy(right)
        wrong['barrier_clear_gap_m'] = 5.0
        with self.assertRaisesRegex(ValueError, 'barrier candidate'):
            audit(spec, left, wrong)

    def test_original_sources_and_delivery_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / 'attempt'
            attempt.mkdir()
            case_id = AID + '__all_present'
            values = {
                'result.json': {'case_id': case_id, 'provenance_kind': 'native',
                                'diagnostic_fixture': False, 'maneuver_completed': True,
                                'measured_values': {'occupancy_frames': 500,
                                                    'vehicle_blueprint_id': 'vehicle.base'}},
                'config.json': {'case_id': case_id, 'law_id': 'LVMC-11-27-010-A',
                                'cell_id': 'C143691', 'actor': 'motor_vehicle_driver',
                                'rate_hz': 20, 'duration_s': 30, 'route_case': 'within',
                                'cameras': [{'name': name} for name in (
                                    'overview', 'approach', 'reference_corner', 'driver_reference')],
                                'source_context_request': dict(BASE_REQUEST)},
                'trail-authority-context.json': {'request': dict(BASE_REQUEST)},
                'candidate-selection.json': {'format': 'worker-candidate-selection',
                                             'case_id': case_id, 'candidate_id': 'primary',
                                             'construction_sha256': 'source-bound-construction'},
                'trail-inventory.json': {'barrier_clear_gap_m': 3.5,
                                         'barrier_blueprint_id': 'static.prop.streetbarrier'},
            }
            for name, value in values.items():
                (attempt / name).write_text(json.dumps(value) + '\n')
            (attempt / 'road.xodr').write_text('<OpenDRIVE/>\n')
            for name, count in (('vehicle-poses.jsonl', 600),
                                ('video_frames.jsonl', 600),
                                ('camera-frames.jsonl', 2400)):
                (attempt / name).write_text('{}\n' * count)
            receipt = {'format': 'worker-delivery-audit', 'passed': True,
                       'case_id': case_id,
                       'source_result_sha256': hashlib.sha256(
                           (attempt / 'result.json').read_bytes()).hexdigest(),
                       'checks': {name: True for name in (
                           'native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion')}}
            receipt_path = root / 'delivery.json'
            receipt_path.write_text(json.dumps(receipt) + '\n')
            self.assertEqual(original(attempt, receipt_path, case_id)['occupancy_frames'], 500)
            (attempt / 'result.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'delivery acceptance absent'):
                original(attempt, receipt_path, case_id)


if __name__ == '__main__':
    unittest.main()
