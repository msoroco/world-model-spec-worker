"""Construct the exact long tour-bus below-boundary primary CPU package."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))
from exception_duration import plan
from exception_road import construct, readback

CASES = ('tour_bus_below', 'tour_bus_at', 'tour_bus_above')


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(case_suffix='tour_bus_below'):
    if case_suffix not in CASES:
        raise ValueError('Unsupported tour-bus boundary case')
    case_id = ROOT.name + '__' + case_suffix
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    case = next(row for row in matrix['cases'] if row['case_id'] == case_id)
    if case['service_class'] != 'tour_bus' or case['activity_request'] != 'passenger_loading':
        raise ValueError('Exact tour-bus branch changed')
    schedule = plan(case)
    if schedule['requested_boundary'] != case_suffix.rsplit('_', 1)[-1] or \
       schedule['stationary_frames'] != {'below': 36000, 'at': 36001, 'above': 36002}[schedule['requested_boundary']]:
        raise ValueError('Tour-bus boundary capture request changed')
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
            ('exception_duration.py', 'exception_duration.py'),
            ('passenger_activity.py', 'passenger_activity.py'),
            ('passenger_spawn.py', 'passenger_spawn.py')):
        files[name] = (NATIVE / native_name).read_text()
    initial = [json.loads(line) for line in files['requested-tracks.jsonl'].splitlines()]
    if len(initial) != 240 or initial[120]['requested_parked'] is not True:
        raise ValueError('Source approach request changed')
    tracks = initial[:schedule['approach_frames']]
    files['requested-tracks.jsonl'] = ''.join(json.dumps(row, separators=(',', ':'),
        allow_nan=False) + '\n' for row in tracks)
    cfg = json.loads(files['config.json'])
    cfg.update(case_id=case_id, selected_case_id=case_id, supported_case_ids=[case_id],
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
        f"self.assertEqual(result['frames'],{schedule['capture_frames']})").replace(
        "self.assertEqual(cfg['sign_classes'], ['no_parking'])",
        "self.assertEqual(cfg['sign_classes'], ['tour_bus', 'shuttle_bus', 'limo'])\n"
        "        self.assertEqual(cfg['native_blueprint'], 'vehicle.mitsubishi.fusorosa')")
    files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
        "if __name__=='__main__': unittest.main()",
        "    def test_compact_long_request_generation(self):\n"
        "        cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())\n"
        "        requests=runner.requests_for_capture(cfg)\n"
        "        first=next(requests)\n"
        "        rows=[first]+list(requests)\n"
        "        self.assertEqual(len(rows),cfg['capture_frames'])\n"
        "        self.assertFalse(rows[119]['requested_parked'])\n"
        "        self.assertTrue(rows[120]['requested_parked'])\n"
        "        self.assertEqual(rows[-1]['frame'],cfg['capture_frames']-1)\n\n"
        "if __name__=='__main__': unittest.main()")
    source['case_id'] = case_id
    source['files'] = [{'path': name, 'content': content} for name, content in files.items()]
    source['status'] = 'draft_selected_cpu'
    source['termination_rules']['requested_frames'] = schedule['capture_frames']
    for channel in source['recording_description']['channels']:
        channel['time_window'] = str(schedule['capture_frames']) + ' frames'
    source['recording_description']['limitations'].append(
        'Passenger boarding, tour-bus livery and the 30-minute legal exception remain unverified.')
    source['measurement_plan'] = {'source': 'retained Native bus, walker, velocity and sign rows',
                                  'finalizer': 'finalize_selected.py', 'legal_verdict': None}
    target = ROOT / 'selected-primary' / case_suffix / 'construction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encode(source))
    return {'case_id': case_id, 'construction_sha256': digest(target.read_text()),
            'capture_frames': schedule['capture_frames'],
            'stationary_frames': schedule['stationary_frames'],
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', default='tour_bus_below', choices=CASES)
    args = parser.parse_args()
    print(encode(build(args.case)), end='')
