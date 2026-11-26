"""Source-shaped CPU joins for the selected pedestrian finalizer.

Dummy videos are byte-binding fixtures and are not media decode or Native proof.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_finalizer():
    spec = importlib.util.spec_from_file_location('c111334_selected', HERE / 'selected_finalize.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Wrong rejection: {error}') from error
        return str(error)
    raise AssertionError(f'Missing rejection: {expected}')


def fixture(folder, suffix):
    folder.mkdir()
    selected = HERE.parent / 'native-selected' / suffix / 'construction.json'
    construction = json.loads(selected.read_text())
    (folder / 'construction.json').write_text(selected.read_text())
    config = next(json.loads(item['content']) for item in construction['files']
                  if item['path'] == 'config.json')
    (folder / 'config.json').write_text(json.dumps(config) + '\n')
    native, mapping = [], []
    for i in range(600):
        y = 4.0 if suffix == 'probe_1' or i < 120 else 4.0 - (i - 119) * .05
        native.append({'video_frame': i, 'native_frame': 1000 + i,
            'time_s': i / 20, 'pedestrian_id': 101,
            'pedestrian_body_polygon_xy_m': [[-.2, y-.2], [.2, y-.2],
                                              [.2, y+.2], [-.2, y+.2]],
            'arrow_head_id': config['arrow_head_id'],
            'other_device_id': config['other_device_id']})
        mapping.append({'video_frame': i, 'native_frame': 1000 + i,
            'carla_frame': 1000 + i, 'time_s': i / 20,
            'source_rgb_sha256': {name: 'a'*64 for name in
                ('overview', 'approach', 'reference_corner', 'driver_reference')}})
    for name, values in (('c111334-native-samples.jsonl', native),
                         ('video_frames.jsonl', mapping)):
        (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in values))
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (folder / (name + '.mkv')).write_bytes(('synthetic-only-' + name).encode())
    bound = {name: sha(folder / name) for name in
             ('c111334-native-samples.jsonl', 'video_frames.jsonl')}
    bound.update({name + '.mkv': sha(folder / (name + '.mkv')) for name in
                  ('overview', 'approach', 'reference_corner', 'driver_reference')})
    review = {'format': 'c111334-device-review-v1', 'case_id': config['case_id'],
        'reviewer': 'synthetic CPU test', 'review_method': 'source-shaped join diagnostic',
        'source_kind': 'synthetic_cpu_fixture', 'original_pixels_reviewed': False,
        'source_sha256': bound, 'green_turn_arrow_alone_by_frame': [True]*600,
        'arrow_faces_pedestrian_by_frame': [True]*600,
        'other_device_permits_proceed_by_frame': [
            suffix == 'permission_before_entry' and i >= 100 for i in range(600)],
        'other_device_governs_pedestrian_by_frame': [True]*600}
    (folder / 'device-review.json').write_text(json.dumps(review) + '\n')
    return review


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set output root under .runtime-work before proving')
    finalizer = load_finalizer()
    with tempfile.TemporaryDirectory(dir=output_root, prefix='source-join-') as temporary:
        base = Path(temporary)
        outputs = {}
        for suffix in ('probe_1', 'probe_2', 'permission_before_entry'):
            folder = base / suffix
            review = fixture(folder, suffix)
            measured = finalizer.source_join_measurement(folder)
            outputs[suffix] = {key: measured[key] for key in
                ('first_highway_entry_frame', 'entry_before_permission',
                 'other_device_permission_at_first_entry', 'green_arrow_alone_facing_throughout')}
            if suffix == 'probe_1':
                assert outputs[suffix]['first_highway_entry_frame'] is None
            else:
                assert outputs[suffix]['first_highway_entry_frame'] == 135
                assert outputs[suffix]['entry_before_permission'] == (suffix == 'probe_2')
            if suffix == 'probe_2':
                negatives = {}
                (folder / 'device-review.json').unlink()
                negatives['missing_review'] = reject(
                    lambda: finalizer.source_join_measurement(folder),
                    'Missing required source: device-review.json')
                (folder / 'device-review.json').write_text(json.dumps(review) + '\n')
                with (folder / 'overview.mkv').open('ab') as stream:
                    stream.write(b'changed')
                negatives['altered_video'] = reject(
                    lambda: finalizer.source_join_measurement(folder),
                    'Device review source binding differs')
                shutil.copyfile(base / 'probe_1' / 'overview.mkv', folder / 'overview.mkv')
                review['source_kind'] = 'original_native'
                review['original_pixels_reviewed'] = True
                (folder / 'device-review.json').write_text(json.dumps(review) + '\n')
                negatives['unsealed_original'] = reject(
                    lambda: finalizer.source_join_measurement(folder),
                    'Original device review requires sealed capture')
    receipt = {'format': 'c111334-selected-source-cpu-v1', 'cases': outputs,
        'negatives': negatives, 'finalizer_sha256': sha(HERE / 'selected_finalize.py'),
        'original_native_observed': False, 'media_decoded': False,
        'legal_verdict_claimed': False}
    target = HERE / 'selected-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'positive_cases': len(outputs), 'negatives': len(negatives),
                      'receipt_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    main()
