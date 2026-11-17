"""Build four exact unsigned emergency no-worker CPU draft candidates.

The firetruck blueprint is a physical construction request, not an observed
emergency identity or a conclusion that the business interval was necessary.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback
from exception_duration import plan

CASE = 'emergency_vehicle_unsigned_no_business'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    exact_id = ROOT.name + '__' + CASE
    case = next(row for row in matrix['cases'] if row['case_id'] == exact_id)
    if (case['service_class'], case['sign_classes'], case['activity_request'],
            case['requested_stationary_duration_s'], case['mailbox_requested']) != (
            'emergency_vehicle', [], None, 12, False):
        raise ValueError('Exact unsigned emergency no-business scope changed')
    road = construct(case)
    if readback(road)['sign_readback']['present']:
        raise ValueError('Unsigned emergency road gained a sign')
    schedule = plan(case)
    if schedule['capture_frames'] != 361 or schedule['stationary_first_frame'] != 120:
        raise ValueError('Emergency business schedule changed')
    records = []
    for candidate in CANDIDATES:
        source = ROOT / ('selected-primary' if candidate == 'primary'
                         else 'selected-fallbacks') / 'tour_bus_no_loading'
        if candidate != 'primary':
            source /= candidate
        package = json.loads((source / 'construction.json').read_text())
        files = {row['path']: row['content'] for row in package['files']}
        config = json.loads(files['config.json'])
        if (config['service_class'], config['native_blueprint'],
                config['requested_approach_frames']) != (
                'tour_bus', 'vehicle.mitsubishi.fusorosa', 120):
            raise ValueError('Source construction changed')
        config.update(case_id=exact_id, selected_case_id=exact_id,
                      supported_case_ids=[exact_id], sign_classes=[],
                      service_class='emergency_vehicle',
                      native_blueprint='vehicle.carlamotors.firetruck',
                      activity_request=None,
                      requested_stationary_duration_s=12,
                      requested_boundary='below',
                      capture_frames=361, stationary_frames=241,
                      frames=361, duration_s=361/20,
                      road_sha256=sha(road),
                      service_identity_source='requested_firetruck_blueprint_native_readback_pending')
        if candidate != 'primary':
            config['risk_trigger'] = config['risk_trigger'].replace(
                'bus body', 'firetruck body').replace('signed curb', 'red curb')
        files['config.json'] = encode(config)
        files['red-curb-road.xodr'] = road
        files['runner.py'] = (ROOT / 'native/emergency_no_business_runner.py').read_text()
        files['finalize_selected.py'] = (ROOT / 'native/finalize_emergency_no_business.py').read_text()
        files['business_absence.py'] = (ROOT / 'native/business_absence.py').read_text()
        files.pop('passenger_absence.py')
        tests = files['tests/test_selected.py']
        tests = tests.replace('36121', '361').replace(
            "['tour_bus', 'shuttle_bus', 'limo']", '[]').replace(
            'vehicle.mitsubishi.fusorosa', 'vehicle.carlamotors.firetruck')
        tests += '\n'
        files['tests/test_selected.py'] = tests
        package['case_id'] = exact_id
        package['files'] = [{'path': path, 'content': content}
                            for path, content in files.items()]
        package['recording_description']['limitations'][-1] = (
            'An empty walker inventory is a no-worker proxy, not proof that no '
            'business occurred. Firetruck body and necessity require Native review.')
        for channel in package['recording_description']['channels']:
            channel['time_window'] = '361 frames'
        package['measurement_plan'] = {
            'source': 'retained Native firetruck body, empty walker inventory, velocity and unsigned red-curb readback',
            'finalizer': 'finalize_selected.py', 'legal_verdict': None}
        package['termination_rules']['requested_frames'] = 361
        target = ROOT / ('selected-primary' if candidate == 'primary'
                         else 'selected-fallbacks') / CASE
        if candidate != 'primary':
            target /= candidate
        target.mkdir(parents=True, exist_ok=True)
        output = target / 'construction.json'
        output.write_text(encode(package))
        records.append({'case_id': exact_id, 'candidate': candidate,
                        'construction': str(output.relative_to(ROOT)),
                        'construction_sha256': sha(output.read_text()),
                        'capture_frames': 361, 'original_native_observed': False,
                        'business_absence_established': False})
    return records


if __name__ == '__main__':
    print(encode(build()), end='')
