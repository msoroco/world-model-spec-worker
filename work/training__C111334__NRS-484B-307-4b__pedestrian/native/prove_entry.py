"""Source-only 600-frame controlled arrow/permission/entry diagnostics."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from measure_entry import FRAMES, SOURCES, measure, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def make(folder, mode):
    folder.mkdir()
    write(folder / 'map.json', {'highway_y_min_m': -3.0,
                                'highway_y_max_m': 3.0,
                                'pedestrian_route_x_m': 0.0})
    write(folder / 'device.json', {'vehicle_head_id': 'turn-arrow-1',
                                   'pedestrian_device_id': 'ped-head-1',
                                   'head_faces_subject': True,
                                   'permission_faces_subject': True})
    rows = []
    for i in range(FRAMES):
        center_y = 4.0 if mode == 'wait' else 4.0-min(max(i-120, 0)*.05, 8.0)
        body = [[x, y] for x, y in ((-.3, center_y-.3), (.3, center_y-.3),
                                     (.3, center_y+.3), (-.3, center_y+.3))]
        rows.append({'frame': i, 'native_frame': 1000+i, 'time_s': i/20,
                     'actor_id': 101, 'actor_kind': 'pedestrian',
                     'vehicle_head_id': 'turn-arrow-1',
                     'pedestrian_device_id': 'ped-head-1',
                     'green_turn_arrow_alone': True,
                     'other_device_permits_proceed': mode == 'permitted' and i >= 100,
                     'body_polygon_xy_m': body})
    (folder / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                                for row in rows))
    write(folder / 'source-manifest.json', {'format': 'c111334-entry-sources-v1',
                                            'sha256': {name: sha(folder / name)
                                                       for name in SOURCES}})
    return rows


def refresh(folder):
    write(folder / 'source-manifest.json', {'format': 'c111334-entry-sources-v1',
                                            'sha256': {name: sha(folder / name)
                                                       for name in SOURCES}})


def reject(folder, expected):
    try:
        measure(folder)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Changed source was accepted: ' + expected)


def prove():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    with tempfile.TemporaryDirectory(prefix='c111334-entry-', dir=ROOT / '.runtime-work') as name:
        scratch = Path(name)
        results = {}
        for mode in ('wait', 'early', 'permitted'):
            make(scratch / mode, mode)
            results[mode] = measure(scratch / mode)
        assert results['wait']['first_highway_entry_frame'] is None
        assert results['wait']['entry_before_permission'] is False
        first_entry = results['early']['first_highway_entry_frame']
        assert 130 <= first_entry <= 136
        assert results['early']['first_other_device_permission_frame'] is None
        assert results['early']['entry_before_permission'] is True
        assert results['permitted']['first_highway_entry_frame'] == first_entry
        assert results['permitted']['first_other_device_permission_frame'] == 100
        assert results['permitted']['entry_before_permission'] is False
        assert results['early']['highway_occupancy_frames'] == results['permitted']['highway_occupancy_frames']
        broken = scratch / 'changed_hash'
        shutil.copytree(scratch / 'early', broken)
        (broken / 'frames.jsonl').write_text((broken / 'frames.jsonl').read_text().replace(
            '"native_frame": 1000', '"native_frame": 9999', 1))
        negatives = {'source_hash': reject(broken, 'source hash mismatch')}
        broken = scratch / 'missing_frame'
        shutil.copytree(scratch / 'early', broken)
        lines = (broken / 'frames.jsonl').read_text().splitlines()
        (broken / 'frames.jsonl').write_text('\n'.join(lines[:-1]) + '\n')
        refresh(broken)
        negatives['missing_frame'] = reject(broken, '600 source frames required')
        broken = scratch / 'wrong_facing'
        shutil.copytree(scratch / 'early', broken)
        device = json.loads((broken / 'device.json').read_text())
        device['head_faces_subject'] = False
        write(broken / 'device.json', device)
        refresh(broken)
        negatives['wrong_facing'] = reject(broken, 'device facing or identity')
        broken = scratch / 'other_arrow_state'
        shutil.copytree(scratch / 'early', broken)
        lines = (broken / 'frames.jsonl').read_text().splitlines()
        row = json.loads(lines[133]);row['green_turn_arrow_alone'] = False
        lines[133] = json.dumps(row, sort_keys=True)
        (broken / 'frames.jsonl').write_text('\n'.join(lines) + '\n')
        refresh(broken)
        negatives['arrow_not_alone'] = reject(broken, 'green turn arrow alone')
    receipt = {'format': 'c111334-pedestrian-entry-source-proof-v1',
               'frames': FRAMES, 'rate_hz': 20, 'duration_s': 30,
               'positives': results, 'negatives': negatives,
               'measurement_script_sha256': sha(HERE / 'measure_entry.py'),
               'original_native_observed': False,
               'physical_signal_visibility_claimed': False,
               'legal_verdict_claimed': False, 'delivery_ready': False}
    target = HERE / 'entry-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'positive_cases': len(results), 'negative_cases': len(negatives),
                      'proof_sha256': sha(target)}))


if __name__ == '__main__':
    prove()
