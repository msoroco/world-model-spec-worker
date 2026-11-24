"""Test exact witness occupancy using source-shaped synthetic CPU inputs."""
import hashlib
import json
from pathlib import Path
import tempfile

from measure_crosswalk import CAMERAS, FRAMES, measure, sha

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]


def write_fixture(folder, suffix):
    folder.mkdir(parents=True)
    case_id = CASE.name + '__' + suffix
    (folder / 'crosswalk-source.json').write_text(json.dumps({
        'case_id': case_id, 'crosswalk_source_kind': 'map_geometry',
        'crosswalk_polygon_xy_m': [[-2, -4], [2, -4], [2, 4], [-2, 4]]}) + '\n')
    with (folder / 'actor-sources.jsonl').open('x') as actors, \
         (folder / 'camera-frames.jsonl').open('x') as cameras:
        for i in range(FRAMES):
            center_x = 5 if suffix == 'witness_1' else 0
            footprint = [[center_x-1, -1], [center_x+1, -1],
                         [center_x+1, 1], [center_x-1, 1]]
            actors.write(json.dumps({'case_id': case_id, 'frame': i,
                'time_s': i / 20, 'ego_speed_mps': 0 if i >= 120 else 4,
                'ego_footprint_xy_m': footprint, 'forced_halt_source': None,
                'direction_source': None}, sort_keys=True) + '\n')
            for name in CAMERAS:
                token = hashlib.sha256(f'{case_id}:{i}:{name}'.encode()).hexdigest()
                cameras.write(json.dumps({'frame': i, 'camera': name,
                    'rgb_sha256': token}, sort_keys=True) + '\n')
    return case_id


def prove():
    scratch = ROOT / '.runtime-work' / 'c229397-450-1e'
    scratch.mkdir(parents=True, exist_ok=True)
    entries = []
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        for suffix, expected in (('witness_1', 0), ('witness_2', 480)):
            folder = Path(tmp) / suffix
            case_id = write_fixture(folder, suffix)
            result = measure(folder, case_id)
            assert result['crosswalk_occupied_while_at_rest_frames'] == expected
            assert result['rest_frames'] == 480
            assert result['legal_verdict'] is None
            assert not result['original_native_observed']
            rejected = []
            for filename in ('actor-sources.jsonl', 'camera-frames.jsonl'):
                path = folder / filename
                source = path.read_text()
                path.write_text('\n'.join(source.splitlines()[:-1]) + '\n')
                try:
                    measure(folder, case_id)
                except ValueError as error:
                    rejected.append(str(error))
                path.write_text(source)
            assert len(rejected) == 2
            entries.append({'case_id': case_id, 'measurement': result,
                            'negative_rejections': rejected})
    receipt = {'format': 'c229397-crosswalk-cpu-proof-v1',
               'assignment_sha256': sha(ROOT / 'inputs' / CASE.name / 'assignment.json'),
               'case_plan_sha256': sha(CASE / 'case-plan.json'),
               'measurement_module_sha256': sha(CASE / 'measure_crosswalk.py'),
               'entries': entries, 'passed': True,
               'original_native_observed': False, 'delivery_ready': False}
    target = CASE / 'offline' / 'crosswalk-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(entries), 'negative_rejections': 4}))


if __name__ == '__main__':
    prove()
