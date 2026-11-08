"""Exact synthetic C422978 controlled-pair positives and tamper negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from compare_saved import compare


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def negative(candidate, kind):
    left = HERE / 'native/saved-fixtures/witness_1' / candidate
    right = HERE / 'native/saved-fixtures/witness_2' / candidate
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c422978-pair-') as temp:
        changed = Path(temp) / 'changed'
        shutil.copytree(right, changed)
        if kind == 'changed_speed':
            path = changed / 'native-observed.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[90]['speed_mps'] = 5.0
            path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        elif kind == 'changed_frame_map':
            path = changed / 'video_frames.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[90]['native_frame'] += 1
            path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        elif kind in ('changed_city_polygon', 'changed_driveway_polygon'):
            path = changed / 'city-context.json'
            packet = json.loads((HERE / 'native/context-fixtures/witness_2' /
                                 candidate / 'city-context.json').read_text())
            if kind == 'changed_city_polygon':
                packet['city_boundary_polygon'][2][0] = 140
            else:
                packet['driveway_crossing_polygons'] = [
                    [[50, 3], [60, 3], [60, 6], [50, 6]]]
            path.write_text(json.dumps(packet, indent=2) + '\n')
        else:
            raise ValueError('Unknown negative')
        retained = HERE / 'native/comparison-negatives' / candidate / kind / path.name
        retained.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, retained)
        try:
            compare(candidate, left, changed,
                    sidewalk_context=path if kind.startswith('changed_city') or
                    kind.startswith('changed_driveway') else None)
        except ValueError as exc:
            message = str(exc)
            if not message.startswith('Measured source hash differs:'):
                raise ValueError('Unexpected negative rejection: ' + message) from exc
            return {'kind': kind, 'rejected': True, 'reason': message,
                    'mutated_source_sha256': sha(path),
                    'retained_source': str(retained.relative_to(HERE))}
        raise ValueError('Changed source accepted')


def prove():
    rows = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        positive = compare(candidate)
        negatives = [negative(candidate, name) for name in
                     ('changed_speed', 'changed_frame_map',
                      'changed_city_polygon', 'changed_driveway_polygon')]
        rows.append({'candidate_id': candidate, 'positive': positive,
                     'negatives': negatives})
        print(candidate, 'controlled positive and four source-tamper negatives passed', flush=True)
    output = {'format': 'c422978-synthetic-controlled-comparison-v1',
              'case_plan_sha256': sha(HERE / 'case-plan.json'),
              'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
              'full_package_summary_sha256': sha(HERE / 'full-package-summary.json'),
              'rows': rows, 'selected_or_original_claimed': False}
    (HERE / 'synthetic-controlled-comparison.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'paired_candidates': len(prove()['rows'])}))
