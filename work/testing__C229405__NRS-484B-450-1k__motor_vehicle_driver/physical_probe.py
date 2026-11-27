"""CPU fixtures for measured travel and ordered Native ownership closure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)
    entry = next(item for item in json.loads((ROOT / 'execution-manifest.json').read_text())['cases']
                 if item['case_id'] == args.case)
    construction = json.loads((ROOT / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / 'construction.json', construction)
    write(folder / 'config.json', config)
    (folder / 'runner.py').write_text(next(item['content'] for item in construction['files']
                                         if item['path'] == 'runner.py'), encoding='utf-8')
    write(folder / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    kind = 'complete_motion' if args.kind == 'lifecycle' else args.kind
    if kind != 'missing_evidence':
        positions = [float(i) for i in range(9)] if kind == 'complete_motion' else [i / 100 for i in range(9)]
        traces, mapping = [], []
        for index, position in enumerate(positions):
            frame, time_s = 700 + index, index / 20
            traces.append({'frame': frame, 'time_s': time_s,
                           'position_m': [position, 0, 0], 'speed_mps': 0})
            mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        for name, rows in (('trace.jsonl', traces), ('video_frames.jsonl', mapping)):
            (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in rows),
                                       encoding='utf-8')
    if args.kind == 'lifecycle':
        seal = seal_capture(folder, frames=9,
                            restoration={'restored': True, 'settings_readback': 'synthetic protocol'},
                            errors=[], encoder_exit_codes={'synthetic': 0})
        native_exit = record_native_exit(folder)
        owner = acknowledge_owner_release(folder, folder / 'owner-release.json', True)
        stage = folder.parent / (folder.name + '-saved')
        stage.mkdir()
        copy_sources(folder, stage)
        if not (stage / 'trace.jsonl').is_file() or not native_exit['capture_seal_sha256'] or not owner['native_exit_sha256']:
            raise ValueError('saved lifecycle closure failed')
        print(' '.join([*seal['events'], 'native_exit', 'owner_released',
                        'saved_processing_started']))
        return
    target = {'target': 'authored excavation approach', 'requested': True,
              'measured': kind == 'complete_motion', 'method': 'synthetic trace',
              'tolerance': 0, 'matched': kind == 'complete_motion',
              'physical_cause_confirmed': False, 'cause_evidence': 'diagnostic trace only'}
    result = physical_result(folder, {'target_checks': [target]})
    write(Path(args.output + '-result.json'), result)
    print(kind, result['physical_checks']['maneuver']['status'],
          result['physical_checks']['maneuver']['sources'])


if __name__ == '__main__':
    main()
