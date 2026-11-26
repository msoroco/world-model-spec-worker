"""Build exact, source-bound lane-change speed constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
TARGETS = {'probe_01': 30.0, 'probe_02': 35.7632, 'probe_03': 36.5}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def make(probe, speed, candidate='primary'):
    case = AID + '__' + probe
    bundle = ROOT/'cases'/probe/candidate
    bundle.mkdir(parents=True, exist_ok=True)
    for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py'):
        (bundle/name).write_bytes((ROOT/'native'/name).read_bytes())
    config = {
        'assignment_id': AID, 'case_id': case, 'selected_case_id': case,
        'supported_case_ids': [AID+'__'+p for p in TARGETS],
        'candidate_id': candidate, 'law_id': 'NRS-484B-600-1e',
        'cell_id': 'C245490', 'actor': 'motor_vehicle_driver',
        'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
        'requested_speed_mps': speed,
        'transition_m': 260 if candidate == 'fallback1' else 200,
        'cameras': [{'name': name, 'width': width, 'height': height,
                     'pose_strategy': 'ego_attached' if name == 'driver_reference' else 'surveyed_world',
                     'fov_deg': 85} for name, width, height in CAMERAS],
        'recording_description': {
            'channels': [
                {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                 'method': method, 'time_window': '600 original frames / 30 seconds',
                 'reference_frame': 'surveyed C245490 same-direction two-lane road',
                 'uncertainty': '50 ms sampling; physical speed and pixels require local review'}
                for name, unit, method in (
                    ('kin.velocity', 'm/s vector', 'post-tick original Native subject velocity'),
                    ('kin.speed', 'mph', 'Euclidean norm of original velocity converted to mph'),
                    ('ru.subject', 'actor identifier', 'original Native actor and blueprint identity'))],
            'context_inputs': [],
            'limitations': ['Controller request is not observed speed',
                            'Synthetic fixture is not physical acceptance']}}
    write(bundle/'config.json', config)
    test = '''import json
import unittest
from pathlib import Path
import runner
from geometry import check as road_check

class ExactConstruction(unittest.TestCase):
    def test_road_and_capture(self):
        self.assertTrue(runner.check()['passed'])
        self.assertTrue(road_check())
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertEqual(len(config['cameras']), 4)
    def test_lane_transition_and_speed_request(self):
        config=json.loads(Path('config.json').read_text())
        speed, lateral=runner.target(config['case_id'],-200,config['transition_m'])
        self.assertEqual(speed,config['requested_speed_mps'])
        self.assertLess(lateral,0)
'''
    (bundle/'tests').mkdir(exist_ok=True)
    (bundle/'tests/test_selected.py').write_text(test)
    names = ('runner.py', 'geometry.py', 'measure.py', 'finalize.py',
             'config.json', 'tests/test_selected.py')
    construction = {
        'format': 'worker-construction', 'assignment_id': AID,
        'case_id': case, 'cell_id': 'C245490', 'law_id': 'NRS-484B-600-1e',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'measurement_plan': {
            'method': '600 original post-tick three-axis Native velocity and lane readbacks',
            'statutory_boundary_mph': 80, 'requested_speed_mps': speed,
            'legal_tolerance_claimed': False},
        'static_checks': ['1700 m same-direction two-lane OpenDRIVE survey',
                          '600 frames at 20 Hz', 'four synchronized original camera views'],
        'termination_rules': ['600 original frames', 'abort on road/lane or camera join failure'],
        'mechanisms': ['surveyed Native lane positions', 'original velocity and lane readback',
                       'longitudinal velocity with smooth lateral transition'],
        'recording_description': config['recording_description'],
        'files': [{'path': name, 'content': (bundle/name).read_text()} for name in names]}
    path = ROOT/'selected-constructions'/(probe+'-'+candidate+'.json')
    write(path, construction)
    return path


def main():
    cases = []
    for probe, speed in TARGETS.items():
        case = AID+'__'+probe
        primary = make(probe, speed)
        candidates = []
        if probe == 'probe_03':
            fallback = make(probe, speed, 'fallback1')
            candidates.append({
                'id': 'fallback1', 'construction': str(fallback.relative_to(ROOT)),
                'construction_sha256': sha(fallback),
                'changed_knobs': ['lane transition length from 200 m to 260 m'],
                'trigger': {'source': 'speed-lane-history.jsonl',
                            'metric': 'destination_lane_entry_and_original_maximum_mph',
                            'failure_condition': 'original Native source has no destination lane entry or fails to exceed the 80 mph boundary'}})
        cases.append({
            'case_id': case, 'kind': 'delivery',
            'construction': str(primary.relative_to(ROOT)),
            'construction_sha256': sha(primary),
            'candidate_risk': {'status': 'physical' if candidates else 'none',
                               'reason': 'At the above-80 request, lateral motion may not finish on the original road; read original speed/lane traces.' if candidates else 'No distinct construction risk identified beyond ordinary physical review.'},
            'candidates': candidates})
    write(ROOT/'selected-draft-execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': sha(Path('runtime/SOURCE-MANIFEST.json')),
        'status': 'selected_cpu_proofs_pending', 'cases': cases,
        'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
