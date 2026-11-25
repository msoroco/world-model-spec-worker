"""Draft replacement selected device bundles with full-law acquisition channels."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
FILES = {
    'runner.py': 'native/device_full_entrypoint.py',
    'device_full_runner.py': 'native/device_full_runner.py',
    'device_full_geometry.py': 'native/device_full_geometry.py',
    'finalize_full_lamp.py': 'native/finalize_full_lamp.py',
    'lamp_full_measure.py': 'native/lamp_full_measure.py',
    'civil_time_measure.py': 'civil_time_measure.py',
    'visibility_measure.py': 'visibility_measure.py',
}
MEASUREMENT_SOURCES = [
    'visibility-trace.jsonl', 'video_frames.jsonl', 'road.xodr',
    'visibility-context.json', 'visibility-pixel-review.json',
    'civil-clock.json', 'civil-time-review.json', 'sun-event-source.json',
    'location-source.json', 'vehicle-lamps.jsonl', 'lamp-context.json',
    'lamp-source-review.json', 'highway-review.json',
    'vehicle-class-review.json', 'device-content-review.json',
    'device-authority-review.json', 'device-placement-review.json',
    'device-timing-review.json', 'overview.mkv', 'approach.mkv',
    'reference_corner.mkv', 'driver_reference.mkv',
]
TEST = '''import json
import unittest
from pathlib import Path
from runner import checked_request, source_clock


class FullDeviceTest(unittest.TestCase):
    def test_native_request(self):
        config = json.loads(Path('config.json').read_text())
        self.assertTrue(checked_request(config)['passed'])

    def test_requires_dated_sun_source(self):
        with self.assertRaises(ValueError):
            source_clock({}, None, None)
'''


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def one(suffix, candidate, recording):
    case = ASSIGNMENT+'__'+suffix
    speed = 3.0 if candidate == 'primary' else 2.8
    config = {'case_id': case, 'selected_case_id': case,
              'supported_case_ids': [case], 'candidate_id': candidate,
              'law_id': 'NRS-484D-100-1', 'cell_id': 'C179824',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
              'required_atoms': [], 'source_packets': [],
              'case': {'case_id': case},
              'boundary_request': {'target_distance_ft': 1000,
                                   'civil_branch': None, 'civil_offset_min': None},
              'lamp_setting_on': suffix == 'controlled_1',
              'weather_name': 'ClearNoon', 'target_speed_mps': speed,
              'cameras': [{'name': name, 'width': width, 'height': height,
                           'pose_strategy': pose, 'fov_deg': 85}
                          for name, width, height, pose in (
                              ('overview', 1920, 1080, 'long-road overview'),
                              ('approach', 1280, 720, 'device approach'),
                              ('reference_corner', 1280, 720, '1000-foot targets'),
                              ('driver_reference', 1280, 720, 'ego forward view'))],
              'recording_description': recording,
              'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    files = [{'path': path, 'content': (HERE/source).read_text()}
             for path, source in FILES.items()]
    files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
                  {'path': 'tests/test_device_full.py', 'content': TEST}])
    construction = {'case_id': case, 'law_id': 'NRS-484D-100-1',
                    'cell_id': 'C179824', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': recording,
                    'measurement_plan': {'entrypoint': 'finalize_full_lamp.py',
                                         'required_sources': list((
                                             'vehicle-lamps.jsonl', 'lamp-context.json',
                                             'lamp-source-review.json',
                                             'visibility-trace.jsonl', 'visibility-context.json',
                                             'visibility-pixel-review.json',
                                             'civil-clock.json', 'civil-time-review.json',
                                             'sun-event-source.json', 'location-source.json',
                                             'road.xodr', 'video_frames.jsonl')),
                                         'source_review_required': True},
                    'static_checks': ['signed 700m paved road',
                                      '1,000-foot person and vehicle targets',
                                      'four cameras and 600 original frames'],
                    'termination_rules': ['600 original frames',
                                          'restore world and destroy owned actors'],
                    'mechanisms': ['original lamp setting and device readback',
                                   'source-bound civil/visibility review',
                                   'independent class and parked review pending'],
                    'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    path = HERE/'draft-device-full'/suffix/candidate/'construction.json'
    dump(path, construction)
    return path


def main():
    recording = json.loads((HERE/'proposals/boundary-cases-draft.json').read_text())['cases'][0]['recording_description']
    entries = []
    for suffix in ('controlled_1', 'controlled_2'):
        primary = one(suffix, 'primary', recording)
        fallback = one(suffix, 'fallback1', recording)
        entries.append({'case_id': ASSIGNMENT+'__'+suffix,
                        'construction': primary.relative_to(HERE).as_posix(),
                        'construction_sha256': hashlib.sha256(primary.read_bytes()).hexdigest(),
                        'measurement_procedure': {'entrypoint': 'finalize_full_lamp.py',
                                                  'output_schema': 'worker-analysis-report-v1'},
                        'measurement_contract': 'cases/full_'+suffix+'/measurement-contract.json',
                        'fixture_recipe': 'work/'+ASSIGNMENT+'/cases/full_'+suffix+'/recipe.json',
                        'candidates': [{'id': 'fallback1',
                                        'construction': fallback.relative_to(HERE).as_posix(),
                                        'construction_sha256': hashlib.sha256(fallback.read_bytes()).hexdigest()}]})
        dump(HERE/'cases'/('full_'+suffix)/'measurement-contract.json',
             {'format': 'worker-measurement-contract',
              'case_id': ASSIGNMENT+'__'+suffix,
              'requirements': [{'disposition_index': 0,
                                'requirement': 'NRS-484D-100-1',
                                'source': 'NRS 484D.100(1)',
                                'output_key': 'lamp_device_measurement',
                                'method': 'reviewed_measure',
                                'value_type': 'object', 'kind': 'measured',
                                'inputs': MEASUREMENT_SOURCES}],
              'negative': {'remove': ['device-authority-review.json'],
                           'error_contains':
                           'Missing required source: device-authority-review.json'}})
    dump(HERE/'draft-device-full-manifest.json',
         {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
          'runtime_manifest_sha256': hashlib.sha256(
              (ROOT/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
          'status': 'construction_draft_cpu_proofs_pending', 'delivery_ready': False,
          'cases': entries})
    print(json.dumps({'passed': True, 'device_cases': len(entries),
                      'draft_constructions': 4,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
