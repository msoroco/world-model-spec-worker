"""Construct the exact long tour-bus below-boundary primary CPU package."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))
from exception_duration import plan
from exception_road import construct, readback

CASE = ROOT.name + '__tour_bus_below'


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    case = next(row for row in matrix['cases'] if row['case_id'] == CASE)
    if case['service_class'] != 'tour_bus' or case['activity_request'] != 'passenger_loading':
        raise ValueError('Exact tour-bus branch changed')
    schedule = plan(case)
    if schedule['requested_boundary'] != 'below' or schedule['stationary_frames'] != 36000:
        raise ValueError('Below-boundary capture request changed')
    source = json.loads((ROOT / 'selected-primary/ordinary_red_signed/construction.json').read_text())
    files = {row['path']: row['content'] for row in source['files']}
    road = construct(case)
    if readback(road)['sign_readback']['displayed_classes'] != case['sign_classes']:
        raise ValueError('Tour-bus sign construction differs')
    files['red-curb-road.xodr'] = road
    for name, native_name in (
            ('runner.py', 'long_exception_runner.py'),
            ('finalize_selected.py', 'finalize_long_exception.py'),
            ('measure_red_curb.py', 'measure_red_curb.py'),
            ('measure_exceptions.py', 'measure_exceptions.py'),
            ('exception_road.py', 'exception_road.py'),
            ('exception_duration.py', 'exception_duration.py')):
        files[name] = (NATIVE / native_name).read_text()
    initial = [json.loads(line) for line in files['requested-tracks.jsonl'].splitlines()]
    if len(initial) != 240 or initial[120]['requested_parked'] is not True:
        raise ValueError('Source approach request changed')
    tracks = initial[:schedule['approach_frames']]
    parked = initial[schedule['approach_frames']]
    for i in range(schedule['approach_frames'], schedule['capture_frames']):
        row = dict(parked, frame=i, time_s=round((i + 1) / 20, 2))
        tracks.append(row)
    files['requested-tracks.jsonl'] = ''.join(json.dumps(row, separators=(',', ':'),
        allow_nan=False) + '\n' for row in tracks)
    cfg = json.loads(files['config.json'])
    cfg.update(case_id=CASE, selected_case_id=CASE, supported_case_ids=[CASE],
               service_class='tour_bus', native_blueprint='vehicle.mitsubishi.fusorosa',
               sign_classes=case['sign_classes'], activity_request=case['activity_request'],
               road_sha256=digest(road), tracks_sha256=digest(files['requested-tracks.jsonl']),
               frames=schedule['capture_frames'], capture_frames=schedule['capture_frames'],
               stationary_frames=schedule['stationary_frames'],
               requested_stationary_duration_s=case['requested_stationary_duration_s'],
               requested_boundary=schedule['requested_boundary'],
               duration_s=schedule['capture_frames'] / 20,
               ordinary_vehicle=False, exception_claimed=False,
               status='draft_selected_cpu')
    files['config.json'] = encode(cfg)
    files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
        "self.assertEqual(result['frames'],240)",
        "self.assertEqual(result['frames'],36120)").replace(
        "self.assertEqual(cfg['sign_classes'], ['no_parking'])",
        "self.assertEqual(cfg['sign_classes'], ['tour_bus', 'shuttle_bus', 'limo'])\n"
        "        self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')")
    source['case_id'] = CASE
    source['files'] = [{'path': name, 'content': content} for name, content in files.items()]
    source['status'] = 'draft_selected_cpu'
    source['termination_rules']['requested_frames'] = schedule['capture_frames']
    for channel in source['recording_description']['channels']:
        channel['time_window'] = str(schedule['capture_frames']) + ' frames'
    source['recording_description']['limitations'].append(
        'Passenger boarding, tour-bus livery and the 30-minute legal exception remain unverified.')
    source['measurement_plan'] = {'source': 'retained Native body, velocity, sign and activity rows',
                                  'finalizer': 'finalize_selected.py', 'legal_verdict': None}
    target = ROOT / 'selected-primary/tour_bus_below/construction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encode(source))
    return {'case_id': CASE, 'construction_sha256': digest(target.read_text()),
            'capture_frames': schedule['capture_frames'],
            'stationary_frames': schedule['stationary_frames'],
            'original_native_observed': False}


if __name__ == '__main__':
    print(encode(build()), end='')
