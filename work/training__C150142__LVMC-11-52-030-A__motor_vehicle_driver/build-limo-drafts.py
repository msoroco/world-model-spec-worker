"""Author provisional limousine-service CPU constructions from signed bus cases.

The Lincoln MKZ is a catalogued sedan. Its chassis does not establish limo
service, licensing, or a limousine body; those remain physical review items.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback

BOUNDARIES = ('below', 'at', 'above', 'no_loading')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
BLUEPRINT = 'vehicle.lincoln.mkz_2020'


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def replace_once(value, before, after):
    if value.count(before) != 1:
        raise ValueError('Source runner or test changed: ' + before)
    return value.replace(before, after)


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    records = []
    for boundary in BOUNDARIES:
        target_case = 'limo_' + boundary
        case_id = ROOT.name + '__' + target_case
        case = next(row for row in matrix['cases'] if row['case_id'] == case_id)
        expected_activity = None if boundary == 'no_loading' else 'passenger_loading'
        expected_duration = {'below': 1799.95, 'at': 1800,
                             'above': 1800.05, 'no_loading': 1800}[boundary]
        if (case['service_class'], case['sign_classes'], case['activity_request'],
                case['requested_stationary_duration_s']) != (
                'limo', ['tour_bus', 'shuttle_bus', 'limo'],
                expected_activity, expected_duration):
            raise ValueError('Frozen limousine branch changed: ' + boundary)
        road = construct(case)
        if readback(road)['sign_readback']['displayed_classes'] != case['sign_classes']:
            raise ValueError('Limousine sign construction differs')
        for candidate in CANDIDATES:
            source = ROOT / ('selected-primary' if candidate == 'primary'
                             else 'selected-fallbacks') / ('shuttle_bus_' + boundary)
            if candidate != 'primary':
                source /= candidate
            package = json.loads((source / 'construction.json').read_text())
            files = {row['path']: row['content'] for row in package['files']}
            config = json.loads(files['config.json'])
            if (config['service_class'], config['native_blueprint'],
                    config['capture_frames']) != (
                    'shuttle_bus', 'vehicle.mitsubishi.fusorosa',
                    {'below': 36120, 'at': 36121, 'above': 36122,
                     'no_loading': 36121}[boundary]):
                raise ValueError('Source signed-bus construction changed')
            config.update(case_id=case_id, selected_case_id=case_id,
                          supported_case_ids=[case_id], service_class='limo',
                          native_blueprint=BLUEPRINT,
                          service_identity_source='authored_limo_service_plan_unverified',
                          road_sha256=sha(road))
            if candidate != 'primary':
                config['risk_trigger'] = config['risk_trigger'].replace(
                    'bus body', 'sedan body')
            files['config.json'] = encode(config)
            files['red-curb-road.xodr'] = road
            runner = replace_once(files['runner.py'],
                                  "cfg.get('service_class') != 'shuttle_bus'",
                                  "cfg.get('service_class') != 'limo'")
            runner = replace_once(runner, 'vehicle.mitsubishi.fusorosa', BLUEPRINT)
            runner = replace_once(runner,
                                  'Shuttle-bus vehicle construction differs',
                                  'Provisional limo-service sedan construction differs')
            files['runner.py'] = runner
            tests = replace_once(files['tests/test_selected.py'],
                                 "self.assertEqual(cfg['service_class'], 'shuttle_bus')",
                                 "self.assertEqual(cfg['service_class'], 'limo')")
            tests = replace_once(tests,
                                 "self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')",
                                 f"self.assertEqual(cfg['native_blueprint'], '{BLUEPRINT}')")
            files['tests/test_selected.py'] = tests
            package['case_id'] = case_id
            package['files'] = [{'path': path, 'content': content}
                                for path, content in files.items()]
            package['recording_description']['limitations'][-1] = (
                ('Passenger absence' if boundary == 'no_loading' else 'Passenger boarding') +
                ', limousine-service identity and the 30-minute legal exception remain '
                'unverified. The Lincoln MKZ is a sedan; this construction does not '
                'establish a limousine body, licensing, or qualifying service.')
            package['measurement_plan']['source'] = (
                'retained Native Lincoln sedan, walker, velocity and sign rows; '
                'limousine service identity remains authored and unverified')
            target = ROOT / ('selected-primary' if candidate == 'primary'
                             else 'selected-fallbacks') / target_case
            if candidate != 'primary':
                target /= candidate
            target.mkdir(parents=True, exist_ok=True)
            output = target / 'construction.json'
            output.write_text(encode(package))
            records.append({'case_id': case_id, 'candidate': candidate,
                            'construction': str(output.relative_to(ROOT)),
                            'construction_sha256': sha(output.read_text()),
                            'capture_frames': config['capture_frames'],
                            'original_native_observed': False,
                            'limousine_service_verified': False})
    return records


if __name__ == '__main__':
    print(encode(build()), end='')
