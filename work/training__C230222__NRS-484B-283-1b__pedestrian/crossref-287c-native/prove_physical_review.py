"""CPU controls for original-source 287(c) review, without claiming a capture."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('physical_review_287c', HERE / 'physical_review.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rejected(action, message):
    try:
        action()
    except ValueError as error:
        if message not in str(error):
            raise
        return
    raise AssertionError('Mutation accepted: ' + message)


def main():
    rows = []
    for label in ('marked', 'unmarked'):
        construction = json.loads((HERE / label / 'construction.json').read_text())
        road = next(x['content'] for x in construction['files'] if x['path'] == 'road.xodr')
        shape = module.inspect_road(road.encode(), label == 'marked')
        assert shape['junction_count'] == shape['device_count'] == 2
        rejected(lambda: module.inspect_road(road.encode(), label != 'marked'),
                 'marked crossing differs')
        entries = []
        frames = []
        for index in range(600):
            entries.append({'native_frame': 1000 + index, 'time_s': index / 20,
                            'adjacent_device_readback': {
                                'south': {'opendrive_id': '28701', 'native_actor_id': 21,
                                          'raw_state': 'green', 'source': 'native_readback'},
                                'north': {'opendrive_id': '28702', 'native_actor_id': 22,
                                          'raw_state': 'red', 'source': 'native_readback'}}})
            frames.append({'video_frame': index, 'native_frame': 1000 + index,
                           'carla_frame': 1000 + index, 'time_s': index / 20})
        assert module.inspect_frames(entries, frames) == {'south': 21, 'north': 22}
        changed = [dict(item) for item in frames]
        changed[99] = {**changed[99], 'native_frame': 7}
        rejected(lambda: module.inspect_frames(entries, changed), 'frame join differs')
        changed_entries = [dict(item) for item in entries]
        changed_entries[99] = {**changed_entries[99], 'adjacent_device_readback': {
            **entries[99]['adjacent_device_readback'],
            'north': {**entries[99]['adjacent_device_readback']['north'], 'raw_state': 'off'}}}
        rejected(lambda: module.inspect_frames(changed_entries, frames), 'readback differs')
        changed_entries[99]['adjacent_device_readback']['north']['raw_state'] = 'red'
        changed_entries[99]['adjacent_device_readback']['north']['native_actor_id'] = 99
        rejected(lambda: module.inspect_frames(changed_entries, frames),
                 'actor changed')
        rows.append({'label': label, 'case_id': construction['case_id'],
                     'construction_sha256': module.sha(HERE / label / 'construction.json'),
                     'authored_road_sha256': hashlib.sha256(road.encode()).hexdigest(),
                     'source_shaped_frame_count': len(entries),
                     'original_native_observed': False})
    report = {'format': 'c230222-287c-physical-review-cpu-proof-v1',
              'physical_review_script_sha256': module.sha(HERE / 'physical_review.py'),
              'cases': rows, 'negative_mutations': ['wrong_marking', 'frame_join',
              'nonoperating_device', 'changed_actor_id'],
              'original_native_observed': False,
              'legal_applicability_conclusion': None}
    path = HERE / 'physical-review-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(rows), 'proof_sha256': module.sha(path)}))


if __name__ == '__main__':
    main()
