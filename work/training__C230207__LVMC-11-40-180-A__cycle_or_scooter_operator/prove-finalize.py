"""Exercise recorded-only finalization and missing-source rejection on fixtures."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE / 'native'))
from finalize import finalize
from geometry import open_drive


def load_fixture():
    spec = importlib.util.spec_from_file_location('source_fixture', HERE / 'prove-measure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fixture


def build_attempt(number, behavior):
    stem = 'walk_cycle' if number == 1 else 'mounted_sidewalk'
    fixture = load_fixture()
    poses, context, frames = fixture('finalize_' + stem, 'unverified', behavior=behavior)
    attempt = ROOT / '.runtime-work/c230207a-finalize' / stem
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    for source, name in ((poses, 'bicycle-poses.jsonl'), (context, 'restriction-context.json'),
                         (frames, 'video_frames.jsonl')):
        shutil.copyfile(source, attempt / name)
    (attempt / 'road.xodr').write_text(open_drive())
    construction = json.loads((HERE / f'draft-mounted-sidewalk/{stem}/primary/construction.json').read_text())
    config = next(f['content'] for f in construction['files'] if f['path'] == 'config.json')
    (attempt / 'config.json').write_text(config)
    shutil.copyfile(HERE / f'draft-mounted-sidewalk/{stem}/measurement-contract.json',
                    attempt / 'measurement-contract.json')
    poses_rows = [json.loads(line) for line in poses.read_text().splitlines()]
    (attempt / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': row['native_frame'], 'time_s': row['time_s'],
        'position': {'x': row['rider_xy_m'][0], 'y': row['rider_xy_m'][1], 'z': 0},
        'position_m': row['rider_xy_m'] + [0], 'speed_mps': 2.3,
        'speed_mph': 2.3 * 2.2369362921, 'heading_deg': 0,
        'velocity_mps': row['velocity_xy_mps'] + [0],
        'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
        'synthetic_diagnostic': True}) + '\n' for row in poses_rows))
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'diagnostic_fixture': True, 'source': 'synthetic_native_sample'}) + '\n')
    return attempt


def main():
    reports = {}
    for number, behavior in ((1, 'walk_cycle'), (2, 'mounted_sidewalk')):
        attempt = build_attempt(number, behavior)
        report = finalize(attempt, attempt / 'analysis-report.json')
        result = json.loads((attempt / 'result.json').read_text())
        assert report['analysis_complete'] and not report['physical_acceptance_claimed']
        assert result['diagnostic_fixture'] and not result['behavior_attempted']
        assert not result['target_checks'][0]['matched']
        assert set(report['measurements']) == {'sidewalk_riding_observation'}
        reports[behavior] = {'case_id': report['case_id'],
                             'posture_unverified_frames': result['measured_values']['posture_unverified_frames'],
                             'source_count': len(report['source_hashes'])}
    negative = build_attempt(1, 'walk_cycle')
    (negative / 'restriction-context.json').unlink()
    try:
        finalize(negative, negative / 'analysis-report.json')
    except ValueError as exc:
        assert 'Missing required source: restriction-context.json' in str(exc), str(exc)
        failure = str(exc)
    else:
        raise AssertionError('missing source accepted')
    return {'passed': True, 'fixture_kind': 'synthetic_native_sample',
            'reports': reports, 'negative_missing_source': failure,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
