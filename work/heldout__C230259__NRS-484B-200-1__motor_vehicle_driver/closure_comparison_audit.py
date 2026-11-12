"""Compare closure-left to the fixed left-half baseline using original sources."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from right_half_measurement import measure

PREFIX = 'heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__'


def source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original closure comparison source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(baseline_root, closure_root):
    baseline, closure = Path(baseline_root), Path(closure_root)
    if baseline.resolve() == closure.resolve():
        raise ValueError('Closure comparison repeats one attempt')
    for root, suffix in ((baseline, 'baseline_left'), (closure, 'closure_left')):
        config = json.loads(source(root, 'config.json').read_text())
        if (config.get('selected_case_id') != PREFIX + suffix or
                (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 80, 4)):
            raise ValueError('Closure comparison exact case or duration differs')
        if [camera.get('name') for camera in config.get('cameras', [])] != [
                'overview', 'approach', 'reference_corner', 'driver_reference']:
            raise ValueError('Closure comparison camera contract differs')
    names = ('ego_road_frames.jsonl', 'road_exception_context.json',
             'video_frames.jsonl', 'trace.jsonl')
    sources = [{name: source(root, name) for name in names} for root in (baseline, closure)]
    body = [rows(item[names[0]]) for item in sources]
    maps = [rows(item[names[2]]) for item in sources]
    traces = [rows(item[names[3]]) for item in sources]
    if len(body[0]) < 3 or any(len(part) != len(body[0]) for part in body + maps + traces):
        raise ValueError('Closure comparison original frame counts differ')
    fixed = ('frame', 'time_s', 'road_id', 'road_center_xy',
             'road_travel_tangent_xy', 'road_width_m')
    for a, b, ma, mb, ta, tb in zip(*body, *maps, *traces):
        if any(a.get(key) != b.get(key) for key in fixed):
            raise ValueError('Closure comparison road/timing conditions changed')
        if ma != mb or (ta['frame'], ta['time_s']) != (tb['frame'], tb['time_s']):
            raise ValueError('Closure comparison frame map or trace timing changed')
    before = json.loads(sources[0][names[1]].read_text())
    after = json.loads(sources[1][names[1]].read_text())
    setup = after.pop('closure_setup', None)
    if (before != after or not isinstance(setup, dict) or
            setup.get('right_half_closure_authority') != 'undecided' or
            setup.get('subject_path') != 'left_half'):
        raise ValueError('Closure comparison changed exception context outside setup')
    measured = [measure(item[names[0]], item[names[1]]) for item in sources]
    if not all(row['whole_body_left_half'] for value in measured
               for row in value['observations']):
        raise ValueError('Closure comparison body left-half position differs')
    devices = rows(source(closure, 'closure_devices.jsonl'))
    if len(devices) != len(body[1]):
        raise ValueError('Closure comparison device source frame count differs')
    for row, frame in zip(devices, body[1]):
        if (row.get('frame'), row.get('time_s')) != (frame['frame'], frame['time_s']):
            raise ValueError('Closure comparison device frame join differs')
    return {'format': 'worker-right-half-closure-comparison',
            'baseline_case_id': PREFIX + 'baseline_left',
            'closure_case_id': PREFIX + 'closure_left',
            'frames': len(body[0]), 'fixed_original_keys': list(fixed) + [
                'video_frames.jsonl', 'trace frame/time', 'exception context except closure_setup'],
            'closure_source_sha256': sha(source(closure, 'closure_devices.jsonl')),
            'passed': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--closure', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.baseline, args.closure)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': result['frames'], 'passed': True}))
