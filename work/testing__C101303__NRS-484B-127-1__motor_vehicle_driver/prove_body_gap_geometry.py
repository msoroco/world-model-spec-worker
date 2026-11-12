"""Source-check the following controller's body-gap to center-spacing offset."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

from body_gap_geometry import native_body_offset, projected_body_offset

FOLDER = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def center(vertices):
    return [sum(vertex[i] for vertex in vertices) / len(vertices) for i in (0, 1)]


def source_offsets(root):
    seal = json.loads((root / 'capture-seal.json').read_text())
    audit = json.loads((root / 'diagnostic-audit.json').read_text())
    if (seal.get('diagnostic_fixture') is not True or
            audit.get('software_checks_passed') is not True or
            audit.get('passed') is not False or audit.get('frames') != 900):
        raise ValueError('Full diagnostic source audit required')
    for name in ('config.json', 'vehicle_history.jsonl', 'video_frames.jsonl'):
        if seal.get('sources', {}).get(name) != sha(root / name):
            raise ValueError('Sealed diagnostic source changed: ' + name)
    if audit.get('original_sources', {}).get('history_sha256') != sha(root / 'vehicle_history.jsonl'):
        raise ValueError('Delivery audit history differs from geometry source')
    config = json.loads((root / 'config.json').read_text())
    direction = json.loads((root / 'road_context.json').read_text())['following_forward_xy']
    rows = [json.loads(line) for line in (root / 'vehicle_history.jsonl').read_text().splitlines() if line]
    if len(rows) != config['rate_hz'] * config['duration_s']:
        raise ValueError('Full original diagnostic body history required')
    offsets = []
    for row in rows:
        ego, lead = row['ego']['body_vertices_xy_m'], row['lead']['body_vertices_xy_m']
        offsets.append(projected_body_offset(center(ego), ego, center(lead), lead,
                                             direction))
    if max(offsets) - min(offsets) > 1e-6:
        raise ValueError('Original body extents changed during diagnostic')
    return {'case_id': config['selected_case_id'], 'requested_gap_m': config['requested_engineering_gap_m'],
            'frames': len(rows), 'projected_body_offset_m': offsets[0],
            'source_sha256': {name: sha(root / name) for name in
                              ('config.json', 'road_context.json', 'vehicle_history.jsonl')}}


def prove(base_root, closer_root):
    cases = [source_offsets(root) for root in (base_root, closer_root)]
    if [row['requested_gap_m'] for row in cases] != [10.0, 7.0]:
        raise ValueError('Selected base/closer engineering grid changed')
    for name in ('source_verified_base', 'source_verified_closer'):
        path = FOLDER / ('construction.json' if name.endswith('base')
                         else 'cases/source_verified_closer/construction.json')
        bundle = json.loads(path.read_text())
        runner = next(item['content'] for item in bundle['files'] if item['path'] == 'runner.py')
        if "target_center_spacing_m=config['requested_engineering_gap_m']+4" not in runner:
            raise ValueError('Reviewed fixed-offset construction changed: ' + name)
    if any(abs(row['projected_body_offset_m'] - 2.0) > 1e-6 for row in cases):
        raise ValueError('Expected original diagnostic body offset changed')

    with tempfile.TemporaryDirectory() as temporary:
        altered = Path(temporary)
        for name in ('capture-seal.json', 'diagnostic-audit.json', 'config.json',
                     'road_context.json', 'vehicle_history.jsonl', 'video_frames.jsonl'):
            shutil.copy2(base_root / name, altered / name)
        history = [json.loads(line) for line in
                   (altered / 'vehicle_history.jsonl').read_text().splitlines() if line]
        history[100]['ego']['body_vertices_xy_m'][0][0] -= 0.25
        (altered / 'vehicle_history.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in history))
        try:
            source_offsets(altered)
        except ValueError as error:
            if 'Sealed diagnostic source changed: vehicle_history.jsonl' not in str(error):
                raise
        else:
            raise ValueError('Changed sealed body geometry was accepted')

    # Exercise the Native-facing helper with a fake actor whose box returns
    # the same sourced vertices, including a rotated route direction.
    def fake_actor(cx, cy, vertices):
        box = SimpleNamespace(get_world_vertices=lambda transform: [
            SimpleNamespace(x=x, y=y) for x, y in vertices])
        return SimpleNamespace(get_location=lambda: SimpleNamespace(x=cx, y=cy),
                               get_transform=lambda: object(), bounding_box=box)
    ego = fake_actor(0, 0, [(-1, -1), (1, -1), (1, 1), (-1, 1)])
    lead = fake_actor(0, 8, [(-1, 7), (1, 7), (1, 9), (-1, 9)])
    if abs(native_body_offset(ego, lead, [0, 1]) - 2.0) > 1e-9:
        raise ValueError('Native box adapter failed rotated route')
    try:
        projected_body_offset((0, 0), [(0, 0)], (0, 8), [(0, 8)], [0, 1])
    except ValueError as error:
        if 'Complete body vertices required' not in str(error):
            raise
    else:
        raise ValueError('Incomplete body geometry was accepted')
    return {'format': 'c101303-source-body-spacing-proof', 'cases': cases,
            'fixed_runner_offset_m': 4.0, 'source_projected_offset_m': 2.0,
            'diagnostic_center_spacing_overstatement_m': 2.0,
            'native_adapter_rotated_test_passed': True,
            'incomplete_body_rejected': True,
            'changed_sealed_body_rejected': True,
            'construction_integrated': False,
            'physical_feasibility_proven': False, 'legal_threshold_asserted': False,
            'helper_sha256': sha(FOLDER / 'body_gap_geometry.py')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-root', type=Path, required=True)
    parser.add_argument('--closer-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prove(args.base_root.resolve(), args.closer_root.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
