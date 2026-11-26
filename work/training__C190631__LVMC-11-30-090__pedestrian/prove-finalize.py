"""Synthetic source-shaped saved finalizer positives/negatives, no physical proof."""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c190631-finalize-fixtures'
sys.path.insert(0, str(HERE / 'native'))
from finalize import finalize


def case_fixture(suffix):
    case = HERE.name + '__probe_' + suffix
    source = ROOT / '.runtime-work/c190631-measure-fixtures' / (
        'sidewalk' if suffix == '01' else 'roadway')
    folder = SCRATCH / suffix
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / 'capture').mkdir()
    for name in ('pedestrian-poses.jsonl', 'surface-geometry.json'):
        shutil.copy2(source / name, folder / name)
    entry = next(e for e in json.loads((HERE / 'draft-roadway-manifest.json').read_text())['cases']
                 if e['case_id'] == case)
    construction = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(f['content'] for f in construction['files']
                             if f['path'] == 'config.json'))
    config['assignment_id'] = HERE.name
    (folder / 'config.json').write_text(json.dumps(config) + '\n')
    (folder / 'construction.json').write_text(json.dumps(construction) + '\n')
    poses = [json.loads(line) for line in (folder / 'pedestrian-poses.jsonl').read_text().splitlines()]
    with (folder / 'trace.jsonl').open('w') as trace, (folder / 'video_frames.jsonl').open('w') as mapped, (folder / 'capture/evidence.jsonl').open('w') as evidence:
        for index, pose in enumerate(poses):
            frame, time_s = pose['native_frame'], pose['time_s']
            trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                'heading_deg': 0, 'position_m': [*pose['pedestrian_xy_m'], 8],
                'velocity_mps': [2, 0, 0]}) + '\n')
            mapped.write(json.dumps({'video_frame': index, 'carla_frame': frame,
                                      'time_s': time_s}) + '\n')
            evidence.write(json.dumps({'original_frame': frame, 'actor_id': 14,
                                        'recording_time_s': time_s}) + '\n')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (folder / (name + '.mkv')).write_text('synthetic video placeholder\n')
    return folder


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    passed = []
    for suffix in ('01', '02'):
        attempt = case_fixture(suffix)
        report = finalize(attempt, SCRATCH / (suffix + '-report.json'))
        assert report['source_complete']
        assert report['measurements']['surface_measurement']['value'][
            ('sidewalk' if suffix == '01' else 'roadway') + '_occupied_frames'] == 600
        passed.append(report['case_id'])
    missing = case_fixture('01')
    (missing / 'surface-geometry.json').unlink()
    try:
        finalize(missing, SCRATCH / 'negative-report.json')
    except ValueError as exc:
        assert str(exc) == 'Missing required source: surface-geometry.json'
        negative_source = str(exc)
    else:
        raise AssertionError('Missing geometry source accepted')
    broken = case_fixture('02')
    frames = (broken / 'video_frames.jsonl').read_text().splitlines()
    first = json.loads(frames[0]); first['carla_frame'] += 1
    frames[0] = json.dumps(first)
    (broken / 'video_frames.jsonl').write_text('\n'.join(frames) + '\n')
    try:
        finalize(broken, SCRATCH / 'wrong-frame-report.json')
    except ValueError as exc:
        assert str(exc) == 'Original pedestrian/frame/capture join differs'
        negative_frame = str(exc)
    else:
        raise AssertionError('Wrong original frame join accepted')
    print(json.dumps({'passed': True, 'case_ids': passed,
                      'negative_source': negative_source,
                      'negative_frame': negative_frame,
                      'fixture_kind': 'synthetic_source_shape_no_video_decode'}, sort_keys=True))


if __name__ == '__main__':
    main()
