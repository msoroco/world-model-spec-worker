"""Materialize exact civil/visibility boundary Native bundles as drafts."""
import json
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCE_FILES = {
    'runner.py': 'native/boundary_entrypoint.py',
    'civil_visibility_runner.py': 'native/civil_visibility_runner.py',
    'visibility_geometry.py': 'native/visibility_geometry.py',
    'finalize_boundary.py': 'native/finalize_boundary.py',
    'civil_time_measure.py': 'civil_time_measure.py',
    'visibility_measure.py': 'visibility_measure.py',
}
TEST = '''import json
import unittest
from pathlib import Path
from runner import checked_request, source_clock


class BoundaryNativeTest(unittest.TestCase):
    def test_configured_probe(self):
        config = json.loads(Path('config.json').read_text())
        self.assertTrue(checked_request(config)['passed'])

    def test_source_gate(self):
        with self.assertRaises(ValueError):
            source_clock({}, 'sunset', 30)
'''


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def build(case, candidate):
    case_id = case['case_id']
    suffix = case_id.removeprefix(ASSIGNMENT+'__')
    request = {'target_distance_ft': 1000,
               'civil_branch': None, 'civil_offset_min': None}
    if suffix.startswith('minutes_after_sunset_'):
        request['civil_branch'] = 'sunset'
        request['civil_offset_min'] = case['probe']['test_value']
    elif suffix.startswith('minutes_before_sunrise_'):
        request['civil_branch'] = 'sunrise'
        request['civil_offset_min'] = case['probe']['test_value']
    elif suffix.startswith('target_reference_distance_ft_'):
        request['target_distance_ft'] = case['probe']['test_value']
    else:
        raise ValueError('unrecognized boundary case: '+suffix)
    config = {'case_id': case_id, 'selected_case_id': case_id,
              'supported_case_ids': [case_id], 'candidate_id': candidate,
              'law_id': 'NRS-484D-100-1', 'cell_id': 'C179824',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20,
              'duration_s': 30, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': case_id}, 'boundary_request': request,
              'weather_name': 'ClearNoon', 'lamp_setting_on': True,
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
    files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
                  {'path': 'tests/test_boundary.py', 'content': TEST}])
    construction = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': case['recording_description'],
                    'measurement_plan': {
                        'entrypoint': 'finalize_boundary.py',
                        'required_sources': list((
                            'visibility-trace.jsonl', 'video_frames.jsonl',
                            'road.xodr', 'visibility-context.json',
                            'visibility-pixel-review.json', 'civil-clock.json',
                            'civil-time-review.json', 'sun-event-source.json',
                            'location-source.json')),
                        'source_review_required': True},
                    'static_checks': ['700m paved road',
                                      'four cameras and 600 original frames',
                                      'source-bound 29/30/31-minute or 999/1000/1001-foot request'],
                    'termination_rules': ['600 original frames',
                                          'restore world and destroy owned actors'],
                    'mechanisms': ['Native moving vehicle and 1,000-foot person/vehicle targets',
                                   'offset-aware civil time bound to dated source',
                                   'original pixel and independent sun review required'],
                    'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    target = HERE/'draft-boundary-cases'/suffix/candidate/'construction.json'
    dump(target, construction)
    return target


def main():
    cases = json.loads((HERE/'proposals/boundary-cases-draft.json').read_text())['cases']
    paths = [build(case, candidate) for case in cases
             for candidate in ('primary', 'fallback1')]
    entries = []
    for case in cases:
        suffix = case['case_id'].removeprefix(ASSIGNMENT+'__')
        pair = [HERE/'draft-boundary-cases'/suffix/candidate/'construction.json'
                for candidate in ('primary', 'fallback1')]
        entries.append({'case_id': case['case_id'],
                        'construction': pair[0].relative_to(HERE).as_posix(),
                        'construction_sha256': hashlib.sha256(pair[0].read_bytes()).hexdigest(),
                        'candidates': [{'id': 'fallback1',
                                        'construction': pair[1].relative_to(HERE).as_posix(),
                                        'construction_sha256': hashlib.sha256(pair[1].read_bytes()).hexdigest()}]})
    dump(HERE/'draft-boundary-manifest.json',
         {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
          'status': 'construction_draft_cpu_proofs_pending', 'delivery_ready': False,
          'cases': entries})
    print(json.dumps({'passed': True, 'draft_constructions': len(paths),
                      'cases': len(cases), 'physical_acceptance_claimed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
