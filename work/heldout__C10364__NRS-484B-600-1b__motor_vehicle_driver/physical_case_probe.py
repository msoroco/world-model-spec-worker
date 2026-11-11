"""One exact alley case synthetic physical/lifecycle source protocol fixture."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from alley_finalizer import analyze, build_result
from physical_probe import exact_config, fixture
from worker_exchange.native_output import physical_result, seal_capture


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion',
                                 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    suffix = args.case.split('__')[-1]
    config = exact_config(suffix)
    if config['selected_case_id'] != args.case:
        raise ValueError('Exact physical fixture identity differs')
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior physical fixture output')
    if args.kind == 'lifecycle':
        output.mkdir(parents=True)
        construction = ROOT / 'cases' / f'construction-{suffix}.json'
        selected = json.loads(construction.read_text())
        (output / 'construction.json').write_bytes(construction.read_bytes())
        (output / 'runner.py').write_text(next(
            item['content'] for item in selected['files']
            if item['path'] == selected['entrypoint']))
        (output / 'trace.jsonl').write_text('{"frame":0,"time_s":0}\n')
        (output / 'video_frames.jsonl').write_text(
            '{"video_frame":0,"carla_frame":0,"time_s":0}\n')
        try:
            seal_capture(output, frames=1, restoration={'restored': False},
                         errors=[], encoder_exit_codes={'overview': 0})
        except ValueError as error:
            if 'verified restoration' not in str(error):
                raise
        else:
            raise ValueError('Premature Native seal was accepted')
        if (output / 'capture-seal.json').exists():
            raise ValueError('Premature Native seal was written')
        seal = seal_capture(output, frames=1, restoration={'restored': True},
                            errors=[], encoder_exit_codes={'overview': 0})
        events = seal['events'] + ['native_exit', 'owner_released',
                                    'saved_processing_started']
        print(json.dumps({'case_id': args.case, 'events': events,
                          'premature_seal_rejected': True,
                          'seal_sha256': sha256((output / 'capture-seal.json').read_bytes()).hexdigest(),
                          'physical_acceptance_claimed': False}, indent=2))
        return
    fixture(output, config, complete=args.kind != 'incomplete_motion')
    if args.kind == 'missing_evidence':
        (output / 'trace.jsonl').unlink()
        result = physical_result(output, {'case_id': args.case, 'target_checks': []})
        expected = 'unverified'
    else:
        result = build_result(output, analyze(output))
        expected = 'met' if args.kind == 'complete_motion' else 'not_met'
    if (result['physical_checks']['maneuver']['status'] != expected
            or result['maneuver_completed'] != (expected == 'met')
            or result.get('physical_acceptance_claimed') is True
            or result.get('legal_acceptance_claimed') is True):
        raise ValueError('Synthetic physical outcome differs from original-source control')
    result['fixture_scope'] = 'synthetic original-shaped CPU protocol; no actual CARLA motion'
    result_path = ROOT / 'physical' / f'{suffix}-{args.kind}-result.json'
    if result_path.exists():
        raise ValueError('Retain prior physical result')
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'status': expected, 'result': str(result_path),
                      'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
