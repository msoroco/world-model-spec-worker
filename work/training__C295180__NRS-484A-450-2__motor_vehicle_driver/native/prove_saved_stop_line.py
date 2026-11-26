"""CPU fixtures for saved stop-line source joins and rejection branches."""
import hashlib
import json
import tempfile
from pathlib import Path

from live_capture import ROAD
from saved_stop_line import measure
from stop_line_request import CASES, FRAMES, request_row


SCRATCH = Path('.runtime-work/c295180-saved-meter')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def build(directory, condition):
    case = CASES[condition]
    native = []
    frame_map = []
    for index in range(FRAMES):
        request = request_row(index, condition)
        native.append({'case_id': case, 'frame': index, 'time_s': index / 20,
                       'native_frame': index + 1000, 'ego': request['ego']})
        frame_map.append({'video_frame': index, 'native_frame': index + 1000,
                          'time_s': index / 20})
    paths = {'native_samples.jsonl': native, 'video_frames.jsonl': frame_map}
    for name, rows in paths.items():
        (directory / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                              for row in rows))
    (directory / 'road.xodr').write_bytes(ROAD.read_bytes())
    write_json(directory / 'stop_reference.json',
               {'stop_sign_present': True, 'governs_ego_lane': True,
                'near_crosswalk_present': False, 'marked_stop_line_x_m': 0,
                'intersection_near_boundary_x_m': 5,
                'source_kind': 'synthetic_cpu_fixture',
                'authored_road_sha256': sha(directory / 'road.xodr')})
    seal(directory, case)
    return case


def seal(directory, case):
    write_json(directory / 'source-seal.json',
               {'format': 'c295180-saved-source-seal-v1', 'case_id': case,
                'source_sha256': {name: sha(directory / name) for name in
                                  ('native_samples.jsonl', 'video_frames.jsonl',
                                   'stop_reference.json', 'road.xodr')}})


def rejected(directory, case, expected):
    try:
        measure(directory, case)
    except ValueError as error:
        if str(error) != expected:
            raise
        return str(error)
    raise AssertionError('Invalid saved source was accepted: ' + expected)


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
        root = Path(temporary)
        results = {}
        for condition in ('full_stop', 'rolling'):
            directory = root / condition
            directory.mkdir()
            case = build(directory, condition)
            results[condition] = measure(directory, case)
        assert results['full_stop']['complete_stop_before_line_diagnostic']
        assert not results['rolling']['complete_stop_before_line_diagnostic']
        directory = root / 'full_stop'
        case = CASES['full_stop']
        negatives = {}
        control = json.loads((directory / 'stop_reference.json').read_text())
        control['stop_sign_present'] = False
        write_json(directory / 'stop_reference.json', control)
        seal(directory, case)
        negatives['missing_sign'] = rejected(
            directory, case, 'Applicable sign, crosswalk, line or intersection source differs')
        control['stop_sign_present'] = True
        write_json(directory / 'stop_reference.json', control)
        seal(directory, case)
        frames = [json.loads(line) for line in
                  (directory / 'video_frames.jsonl').read_text().splitlines()]
        frames[8]['native_frame'] += 1
        (directory / 'video_frames.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in frames))
        seal(directory, case)
        negatives['bad_frame_join'] = rejected(
            directory, case, 'Original video/Native frame join differs')
        frames[8]['native_frame'] -= 1
        (directory / 'video_frames.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in frames))
        seal(directory, case)
        with (directory / 'native_samples.jsonl').open('a') as handle:
            handle.write('{}\n')
        negatives['stale_source_hash'] = rejected(
            directory, case, 'Saved source hash differs: native_samples.jsonl')
        road_dir = root / 'bad_road'
        road_dir.mkdir()
        bad_case = build(road_dir, 'full_stop')
        road_path = road_dir / 'road.xodr'
        road_path.write_text(road_path.read_text().replace(
            'clearly-marked-stop-line', 'absent-line'))
        reference = json.loads((road_dir / 'stop_reference.json').read_text())
        reference['authored_road_sha256'] = sha(road_path)
        write_json(road_dir / 'stop_reference.json', reference)
        seal(road_dir, bad_case)
        negatives['missing_road_line'] = rejected(
            road_dir, bad_case, 'Clearly marked transverse stop-line object absent')
        motion_dir = root / 'bad_motion'
        motion_dir.mkdir()
        motion_case = build(motion_dir, 'full_stop')
        motion = [json.loads(line) for line in
                  (motion_dir / 'native_samples.jsonl').read_text().splitlines()]
        for row in motion[:20]:
            row['ego']['speed_mps'] = 0
        (motion_dir / 'native_samples.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in motion))
        seal(motion_dir, motion_case)
        negatives['inconsistent_motion'] = rejected(
            motion_dir, motion_case, 'Original ego trajectory and speed source differ')
        return {'format': 'c295180-saved-meter-cpu-proof-v1',
                'positive': results, 'negative_rejections': negatives,
                'physical_completion_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2, sort_keys=True))
