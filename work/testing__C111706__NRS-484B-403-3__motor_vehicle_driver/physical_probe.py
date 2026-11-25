"""Source-bound synthetic U-turn travel and Native closure protocol proof."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def fixture(path, config, construction, kind):
    path.mkdir()
    write(path / 'config.json', config)
    write(path / 'construction.json', construction)
    (path / 'runner.py').write_text(next(
        file['content'] for file in construction['files'] if file['path'] == 'runner.py'))
    write(path / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    if kind == 'missing_evidence':
        return
    distance = 120.0 if kind == 'complete_motion' else 1.0
    rows = []
    mapping = []
    for index in range(900):
        fraction = index / 899
        frame, time_s = 300 + index, index / 20
        x = distance * (1 - fraction)
        y = (4.0 if kind == 'complete_motion' else 0.1) * (1 - abs(2 * fraction - 1))
        rows.append({'frame': frame, 'time_s': time_s,
                     'position': {'x': x, 'y': y, 'z': 0},
                     'position_m': [x, y, 0],
                     'heading_deg': 180 * fraction, 'speed_mps': distance / 45})
        mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
    for name, values in [('trace.jsonl', rows), ('video_frames.jsonl', mapping)]:
        (path / name).write_text(''.join(json.dumps(row) + '\n' for row in values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == args.case)
    construction = json.loads((ROOT / entry['construction']).read_text())
    config = json.loads(next(file['content'] for file in construction['files']
                             if file['path'] == 'config.json'))
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    for kind, expected in [('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')]:
        folder = root / kind
        fixture(folder, config, construction, kind)
        result = physical_result(folder, {'target_checks': [{
            'target': 'observed U-turn travel progression',
            'requested': True, 'measured': kind == 'complete_motion',
            'method': 'CPU original-shaped trace', 'tolerance': 0,
            'matched': kind == 'complete_motion',
            'physical_cause_confirmed': False,
            'cause_evidence': 'diagnostic trace only'}]})
        if (result['physical_checks']['maneuver']['status'] != expected or
                result['maneuver_completed'] != (expected == 'met')):
            raise ValueError('physical outcome mismatch: ' + kind)
        write(ROOT / ('physical-' + args.case.rsplit('__', 1)[-1] + '-' + kind + '.json'), result)
        print(kind, expected, sorted(result['physical_checks']['maneuver']['sources']))
    complete = root / 'complete_motion'
    seal_capture(complete, frames=900,
                 restoration={'restored': True, 'settings_readback': 'CPU protocol fixture'},
                 errors=[], encoder_exit_codes={'diagnostic': 0})
    record_native_exit(complete)
    acknowledge_owner_release(complete, complete / 'owner-release.json', True)
    stage = root / 'saved_stage'
    stage.mkdir()
    copy_sources(complete, stage)
    print('lifecycle capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started')


if __name__ == '__main__':
    main()
