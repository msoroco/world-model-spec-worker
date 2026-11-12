"""Build a matched 900-frame near diagnostic and prove its source comparison."""
import argparse
import copy
import json
import shutil
from pathlib import Path

from far_near_comparison_audit import SOURCES, compare, read, rows, sha


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prove(far_root, output_root):
    if output_root.exists():
        raise ValueError('Use a fresh comparison diagnostic root')
    near = output_root / 'near'
    near.mkdir(parents=True)
    for name in ('config.json', 'intersection_geometry.json', 'video_frames.jsonl'):
        shutil.copy2(far_root / name, near / name)
    config = read(near / 'config.json')
    config['selected_case_id'] = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_no_yield'
    write(near / 'config.json', config)
    history = rows(far_root / 'interaction_history.jsonl')
    for row in history:
        actor = row['oncoming']
        actor['position_xy_m'][0] -= 15
        for vertex in actor['body_vertices_xy_m']:
            vertex[0] -= 15
    (near / 'interaction_history.jsonl').write_text(
        ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in history))
    write(near / 'capture-seal.json',
          {'diagnostic_fixture': True,
           'sources': {name: sha(near / name) for name in SOURCES}})
    result = compare(far_root, near)
    if result['frames'] != 900 or result['physical_acceptance_claimed'] is not False:
        raise ValueError('Comparison diagnostic made an invalid claim')
    tampered = output_root / 'tampered'
    shutil.copytree(near, tampered)
    altered = copy.deepcopy(history)
    altered[40]['ego_left_indicator'] = False
    (tampered / 'interaction_history.jsonl').write_text(
        ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in altered))
    try:
        compare(far_root, tampered)
    except ValueError as error:
        if 'Paired original source differs from capture seal: interaction_history.jsonl' not in str(error):
            raise
    else:
        raise ValueError('Tampered comparison original was accepted')
    write(output_root / 'comparison-proof.json', result)
    print(json.dumps({'receipt': str(output_root / 'comparison-proof.json'),
                      'receipt_sha256': sha(output_root / 'comparison-proof.json'),
                      'tampered_original_rejected': True, **result}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--far-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    prove(args.far_root.resolve(), args.output_root.resolve())


if __name__ == '__main__':
    main()
