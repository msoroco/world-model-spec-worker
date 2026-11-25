"""Independent synthetic controlled-pair source and construction comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line]


def audit():
    paths = [HERE / f'diagnostic-controlled_{index}.json' for index in (1, 2)]
    pair = [json.loads(path.read_text()) for path in paths]
    first, second = pair
    if set(first['files']) != set(second['files']):
        raise ValueError('controlled pair changed original source inventory')
    changed = [name for name in first['files'] if first['files'][name] != second['files'][name]]
    if changed != ['device-original.jsonl']:
        raise ValueError('controlled pair changed source outside device instruction: ' + str(changed))
    if first['graphs'] != second['graphs'] or first['videos'] != second['videos']:
        raise ValueError('controlled pair changed original graphs or camera source recipes')
    left, right = [rows(spec['files']['device-original.jsonl']) for spec in pair]
    people = rows(first['files']['pedestrian-original.jsonl'])
    if not len(left) == len(right) == len(people):
        raise ValueError('controlled pair source frame count differs')
    if len(left) != 600 or len(people) != 600:
        raise ValueError('controlled pair does not retain 600 frames')
    differences = []
    for index, (a, b) in enumerate(zip(left, right)):
        left_fixed = dict(a)
        right_fixed = dict(b)
        left_fixed.pop('displayed_instruction')
        right_fixed.pop('displayed_instruction')
        if left_fixed != right_fixed:
            raise ValueError('device identity/time/source changed')
        if a['displayed_instruction'] != b['displayed_instruction']:
            differences.append(index)
    if differences != list(range(100, 160)):
        raise ValueError('device contrast differs from controlled 60-frame window')
    entry = [i for i, row in enumerate(people) if row['road_entry_proxy_observed']]
    if entry != [100] or (left[100]['displayed_instruction'],
                          right[100]['displayed_instruction']) != ('diagonal_walk', 'diagonal_dont_walk'):
        raise ValueError('first-entry original device contrast absent')
    result = {'format': 'c109166-controlled-comparison-cpu-proof-v1',
              'diagnostic_spec_sha256': [sha(path) for path in paths],
              'frame_count_each': 600, 'changed_device_frames': [100, 159],
              'changed_device_frame_count': 60,
              'first_entry_video_frame': 100,
              'fixed_original_source_files': sorted(set(first['files']) - {'device-original.jsonl'}),
              'same_graph_recipe': True, 'same_video_recipe': True,
              'original_native_executed': False,
              'physical_or_legal_acceptance_claimed': False}
    output = HERE / 'comparison-proof.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'sha256': sha(output)}))


if __name__ == '__main__':
    audit()
