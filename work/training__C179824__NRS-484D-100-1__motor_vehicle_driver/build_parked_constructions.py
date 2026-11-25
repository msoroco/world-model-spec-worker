"""Materialize two exact parked exception Native construction drafts."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCE_FILES = {
    'runner.py': 'native/parked_entrypoint.py',
    'parked_runner.py': 'native/parked_runner.py',
    'device_full_geometry.py': 'native/device_full_geometry.py',
    'finalize_parked.py': 'native/finalize_parked.py',
    'lamp_full_measure.py': 'native/lamp_full_measure.py',
    'civil_time_measure.py': 'civil_time_measure.py',
    'visibility_measure.py': 'visibility_measure.py',
    'parked_exception_measure.py': 'parked_exception_measure.py',
}
TEST = '''import json
import unittest
from pathlib import Path
from runner import checked_request, source_clock


class ParkedNativeTest(unittest.TestCase):
    def test_configured_probe(self):
        config = json.loads(Path('config.json').read_text())
        self.assertTrue(checked_request(config)['passed'])

    def test_source_gate(self):
        with self.assertRaises(ValueError):
            source_clock({})
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def build(case, candidate):
    case_id = case['case_id']
    suffix = case_id.removeprefix(ASSIGNMENT+'__')
    lamp_on = case['variable_assignments']['requested_lamp_setting_on']['value']
    config = {'case_id': case_id, 'selected_case_id': case_id,
              'supported_case_ids': [case_id], 'candidate_id': candidate,
              'law_id': 'NRS-484D-100-1', 'cell_id': 'C179824',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20,
              'duration_s': 30, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': case_id},
              'parked_request': {'lamp_setting_on': lamp_on,
                                 'target_distance_ft': 1000,
                                 'travel_frames': 450, 'parked_frames': 100},
              'weather_name': 'ClearNoon', 'lamp_setting_on': lamp_on,
              'target_speed_mps': 3.0 if candidate == 'primary' else 2.8,
              'cameras': [{'name': name, 'width': width, 'height': height,
                           'fov_deg': 85}
                          for name, width, height in (
                              ('overview', 1920, 1080), ('approach', 1280, 720),
                              ('reference_corner', 1280, 720),
                              ('driver_reference', 1280, 720))],
              'recording_description': case['recording_description'],
              'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    files = [{'path': target, 'content': (HERE/source).read_text()}
             for target, source in SOURCE_FILES.items()]
    files += [{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
              {'path': 'tests/test_parked.py', 'content': TEST}]
    construction = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': case['recording_description'],
                    'measurement_plan': {
                        'entrypoint': 'finalize_parked.py',
                        'required_sources': [
                            'parked-trace.jsonl', 'parked-exception-review.json',
                            'nrs-484d-165-source.json', 'parked-highway-review.json',
                            'parked-status-review.json', 'visibility-trace.jsonl',
                            'vehicle-lamps.jsonl', 'video_frames.jsonl',
                            'road.xodr', 'civil-clock.json', 'sun-event-source.json'],
                        'source_review_required': True},
                    'static_checks': ['700m paved road and mapped shoulder',
                                      'four cameras and 600 original frames',
                                      'final 100 frames stationary on shoulder'],
                    'termination_rules': ['600 original frames',
                                          'restore world and destroy owned actors'],
                    'mechanisms': ['Native travel to mapped shoulder and stop',
                                   'offset-aware civil time bound to dated source',
                                   'independent source and pixel review required'],
                    'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    target = HERE/'draft-parked-cases'/suffix/candidate/'construction.json'
    dump(target, construction)
    return target


def main():
    cases = json.loads((HERE/'proposals/parked-exception-cases-draft.json').read_text())['cases']
    paths = [build(case, candidate) for case in cases
             for candidate in ('primary', 'fallback1')]
    entries = []
    for case in cases:
        suffix = case['case_id'].removeprefix(ASSIGNMENT+'__')
        pair = [HERE/'draft-parked-cases'/suffix/candidate/'construction.json'
                for candidate in ('primary', 'fallback1')]
        entries.append({'case_id': case['case_id'],
                        'construction': pair[0].relative_to(HERE).as_posix(),
                        'construction_sha256': sha(pair[0]),
                        'candidates': [{'id': 'fallback1',
                                        'construction': pair[1].relative_to(HERE).as_posix(),
                                        'construction_sha256': sha(pair[1])}]})
    dump(HERE/'draft-parked-manifest.json',
         {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
          'status': 'construction_draft_cpu_proofs_pending', 'delivery_ready': False,
          'cases': entries})
    print(json.dumps({'passed': True, 'draft_constructions': len(paths),
                      'cases': len(cases), 'physical_acceptance_claimed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
