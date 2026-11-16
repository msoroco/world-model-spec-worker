"""Construct four shuttle service cases with three alternatives per case."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = ('below', 'at', 'above', 'no_loading')


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    result = []
    for boundary in BOUNDARIES:
     source_case = 'tour_bus_' + boundary
     target_case = 'shuttle_bus_' + boundary
     target_id = ROOT.name + '__' + target_case
     case = next(row for row in matrix['cases'] if row['case_id'] == target_id)
     if (case['service_class'], case['activity_request'],
             case['requested_stationary_duration_s'], case['sign_classes']) != (
             'shuttle_bus', None if boundary == 'no_loading' else 'passenger_loading',
             {'below': 1799.95, 'at': 1800, 'above': 1800.05,
              'no_loading': 1800}[boundary], ['tour_bus', 'shuttle_bus', 'limo']):
         raise ValueError('Frozen shuttle-bus boundary target changed: ' + boundary)
     for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        source = (ROOT / ('selected-primary' if candidate == 'primary' else
                          'selected-fallbacks') / source_case)
        if candidate != 'primary':
            source /= candidate
        package = json.loads((source / 'construction.json').read_text())
        files = {row['path']: row['content'] for row in package['files']}
        config = json.loads(files['config.json'])
        if (config['service_class'], config['native_blueprint'],
                config['capture_frames']) != ('tour_bus',
                                              'vehicle.mitsubishi.fusorosa',
                                              {'below': 36120, 'at': 36121,
                                               'above': 36122, 'no_loading': 36121}[boundary]):
            raise ValueError('Source bus construction changed')
        config['case_id'] = target_id
        config['selected_case_id'] = target_id
        config['supported_case_ids'] = [target_id]
        config['service_class'] = 'shuttle_bus'
        config['service_identity_source'] = 'authored_shuttle_service_plan_unverified'
        files['config.json'] = encoded(config)
        runner = files['runner.py']
        old = "cfg.get('service_class') != 'tour_bus'"
        if runner.count(old) != 1:
            raise ValueError('Source bus runner check changed')
        files['runner.py'] = runner.replace(old,
                                            "cfg.get('service_class') != 'shuttle_bus'").replace(
                                                'Tour-bus vehicle construction differs',
                                                'Shuttle-bus vehicle construction differs')
        tests = files['tests/test_selected.py']
        if "self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')" not in tests:
            raise ValueError('Source bus test changed')
        files['tests/test_selected.py'] = tests.replace(
            "self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')",
            "self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')\n"
            "        self.assertEqual(cfg['service_class'], 'shuttle_bus')")
        package['case_id'] = target_id
        package['files'] = [{'path': path, 'content': content}
                            for path, content in files.items()]
        package['recording_description']['limitations'][-1] = (
            ('Passenger absence' if boundary == 'no_loading' else 'Passenger boarding') +
            ', shuttle service identity and the 30-minute legal exception remain '
            'unverified. A bus chassis alone does not establish service class.')
        package['measurement_plan']['source'] = (
            'retained Native shuttle-service bus, walker, velocity and sign rows; '
            'service identity remains authored and unverified')
        target = (ROOT / ('selected-primary' if candidate == 'primary' else
                          'selected-fallbacks') / target_case)
        if candidate != 'primary':
            target /= candidate
        target.mkdir(parents=True, exist_ok=True)
        path = target / 'construction.json'
        path.write_text(encoded(package))
        result.append({'case_id': target_id, 'candidate': candidate,
                       'construction': str(path.relative_to(ROOT)),
                       'construction_sha256': sha(path.read_text()),
                       'capture_frames': config['capture_frames'],
                       'original_native_observed': False})
    return result


if __name__ == '__main__':
    print(encoded(build()), end='')
