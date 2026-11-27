"""CPU proof of the pinned physical checker and lifecycle ordering; synthetic only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ORDER = ('capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started')


def lifecycle(events):
    if tuple(events) != ORDER:
        raise ValueError('Saved processing precedes Native ownership closure')
    return True


def assess(fixture, config, kind):
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Physical diagnostic scratch must remain in .runtime-work')
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    if repo is None:
        raise ValueError('Worker runtime unavailable')
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        root = Path(directory)
        (root / 'config.json').write_text(Path(config).read_text())
        shutil.copyfile(Path(fixture) / 'video_frames.jsonl', root / 'video_frames.jsonl')
        if kind != 'missing_evidence':
            trace = [json.loads(line) for line in (Path(fixture) / 'trace.jsonl').read_text().splitlines()]
            if kind == 'incomplete_motion':
                x = trace[0]['position_m'][0]
                for row in trace:
                    row['position_m'][0] = x
                    row['position']['x'] = x
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
        cfg = json.loads((root / 'config.json').read_text())
        outcome = assess_physical(root, cfg)
        status = outcome['physical_checks']['maneuver']['status']
        return {'case_id': cfg['case_id'], 'fixture_kind': kind,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'physical_checks': outcome['physical_checks'],
            'maneuver_completed': outcome['maneuver_completed'],
            'realized_observables': outcome['realized_observables'],
            'synthetic_mutation': kind,
            'expected_status_matched': status == {
                'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture')
    parser.add_argument('--config')
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + (ORDER[-1], ORDER[-2]))
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError('Premature saved processing accepted')
        print('Native ownership closure precedes saved processing')
    else:
        result = assess(args.fixture, args.config, args.kind)
        if not result['expected_status_matched']:
            raise ValueError('Pinned physical checker returned unexpected outcome')
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(args.kind, result['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
