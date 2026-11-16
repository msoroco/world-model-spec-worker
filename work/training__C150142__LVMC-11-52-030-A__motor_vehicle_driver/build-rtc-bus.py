"""Construct signed RTC bus boundary cases and three alternatives per case."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback

BOUNDARIES = ('below', 'at', 'above', 'no_loading')


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    result = []
    for boundary in BOUNDARIES:
        source_case = 'shuttle_bus_' + boundary
        target_case = 'rtc_bus_' + boundary
        target_id = ROOT.name + '__' + target_case
        case = next(row for row in matrix['cases'] if row['case_id'] == target_id)
        if (case['service_class'], case['sign_classes'], case['activity_request'],
                case['requested_stationary_duration_s']) != (
                'rtc_bus', ['rtc_bus'],
                None if boundary == 'no_loading' else 'passenger_loading',
                {'below': 1799.95, 'at': 1800, 'above': 1800.05,
                 'no_loading': 1800}[boundary]):
            raise ValueError('Frozen RTC bus case changed: ' + boundary)
        road = construct(case)
        if readback(road)['sign_readback']['displayed_classes'] != ['rtc_bus']:
            raise ValueError('RTC sign road construction differs')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = (ROOT / ('selected-primary' if candidate == 'primary' else
                              'selected-fallbacks') / source_case)
            if candidate != 'primary':
                source /= candidate
            package = json.loads((source / 'construction.json').read_text())
            files = {row['path']: row['content'] for row in package['files']}
            config = json.loads(files['config.json'])
            if (config['service_class'], config['sign_classes']) != (
                    'shuttle_bus', ['tour_bus', 'shuttle_bus', 'limo']):
                raise ValueError('Source signed bus construction changed')
            config['case_id'] = target_id
            config['selected_case_id'] = target_id
            config['supported_case_ids'] = [target_id]
            config['service_class'] = 'rtc_bus'
            config['service_identity_source'] = 'authored_rtc_service_plan_unverified'
            config['sign_classes'] = ['rtc_bus']
            config['road_sha256'] = sha(road)
            files['config.json'] = encoded(config)
            files['red-curb-road.xodr'] = road
            runner = files['runner.py']
            old = "cfg.get('service_class') != 'shuttle_bus'"
            if runner.count(old) != 1:
                raise ValueError('Source bus runner service check changed')
            files['runner.py'] = runner.replace(
                old, "cfg.get('service_class') != 'rtc_bus'").replace(
                'Shuttle-bus vehicle construction differs',
                'RTC-bus vehicle construction differs')
            tests = files['tests/test_selected.py']
            if "self.assertEqual(cfg['service_class'], 'shuttle_bus')" not in tests:
                raise ValueError('Source bus test changed')
            files['tests/test_selected.py'] = tests.replace(
                "self.assertEqual(cfg['service_class'], 'shuttle_bus')",
                "self.assertEqual(cfg['service_class'], 'rtc_bus')").replace(
                "self.assertEqual(cfg['sign_classes'], ['tour_bus', 'shuttle_bus', 'limo'])",
                "self.assertEqual(cfg['sign_classes'], ['rtc_bus'])")
            package['case_id'] = target_id
            package['files'] = [{'path': name, 'content': content}
                                for name, content in files.items()]
            package['recording_description']['limitations'][-1] = (
                ('Passenger absence' if boundary == 'no_loading' else 'Passenger boarding') +
                ', RTC service identity and the 30-minute legal exception remain '
                'unverified. A bus chassis alone does not establish service class.')
            package['measurement_plan']['source'] = (
                'retained Native bus, walker, velocity and RTC sign rows; '
                'RTC service identity remains authored and unverified')
            target = ROOT / ('selected-primary' if candidate == 'primary' else
                             'selected-fallbacks') / target_case
            if candidate != 'primary':
                target /= candidate
            target.mkdir(parents=True, exist_ok=True)
            output = target / 'construction.json'
            output.write_text(encoded(package))
            result.append({'case_id': target_id, 'candidate': candidate,
                           'construction': str(output.relative_to(ROOT)),
                           'construction_sha256': sha(output.read_text()),
                           'capture_frames': config['capture_frames'],
                           'original_native_observed': False})
    return result


if __name__ == '__main__':
    print(encoded(build()), end='')
