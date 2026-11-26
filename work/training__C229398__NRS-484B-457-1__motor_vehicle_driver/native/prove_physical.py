"""CPU physical progress and ownership-order diagnostics; no Native claim."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def check_lifecycle(events):
    required = ['capture_finished', 'encoders_closed', 'restoration_verified',
                'native_exit', 'owner_released', 'saved_processing_started']
    if events != required:
        raise ValueError('Saved processing precedes Native ownership closure')
    return required


def run(case_id, source, scratch, output):
    from scenario_pipeline.worker_exchange.native_output import physical_result
    source, scratch, output = map(Path, (source, scratch, output))
    if scratch.exists():
        raise ValueError('Use fresh scratch for physical fixtures')
    scratch.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    assignment = Path(__file__).resolve().parents[1]
    trace = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
    base = json.loads((source / 'result.json').read_text())
    fixtures = []
    for kind, expected in (('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        attempt = scratch / kind
        attempt.mkdir()
        for name in ('config.json', 'video_frames.jsonl'):
            shutil.copyfile(source / name, attempt / name)
        if kind != 'missing_evidence':
            rows = trace if kind == 'complete_motion' else []
            if kind == 'incomplete_motion':
                for row in trace:
                    changed = dict(row)
                    changed['position'] = dict(trace[0]['position'])
                    changed['position_m'] = list(trace[0]['position_m'])
                    rows.append(changed)
            (attempt / 'trace.jsonl').write_text(''.join(
                json.dumps(row, allow_nan=False) + '\n' for row in rows))
        result = physical_result(attempt, dict(base))
        observed = result['physical_checks']['maneuver']['status']
        if observed != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError(f'{kind} physical classification {observed}, wanted {expected}')
        if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
            raise ValueError('Physical diagnostic provenance changed')
        result_path = output / f'{case_id}-{kind}-result.json'
        log_path = output / f'{case_id}-{kind}.log'
        put(result_path, result)
        log_path.write_text(f'{kind}: {observed}; synthetic fixture; no legal verdict\n')
        fixtures.append({'kind': kind,
            'command': f'prove_physical.py --case {case_id} --fixture {kind}',
            'exit_code': 0, 'log': str(log_path.resolve().relative_to(assignment)),
            'log_sha256': sha(log_path),
            'result': str(result_path.resolve().relative_to(assignment)),
            'result_sha256': sha(result_path)})
    lifecycle_log = output / f'{case_id}-lifecycle.log'
    ordered = check_lifecycle(['capture_finished', 'encoders_closed',
        'restoration_verified', 'native_exit', 'owner_released',
        'saved_processing_started'])
    try:
        check_lifecycle(ordered[:-2] + ['saved_processing_started'])
    except ValueError as error:
        if 'precedes Native ownership closure' not in str(error):
            raise
    else:
        raise ValueError('Early saved processing unexpectedly accepted')
    lifecycle_log.write_text('Synthetic CPU event-order model accepted complete order and rejected saved processing before owner release\n')
    lifecycle = {'events': ordered, 'exit_code': 0,
        'log': str(lifecycle_log.resolve().relative_to(assignment)),
        'log_sha256': sha(lifecycle_log),
        'synthetic_fixture': True, 'actual_owner_release_claimed': False}
    exact_construction = assignment / 'native' / 'bundles' / case_id.rsplit('__', 1)[-1] / 'construction.json'
    return {'format': 'c229398-physical-preparation-v1', 'case_id': case_id,
        'construction_sha256': sha(exact_construction),
        'fixtures': fixtures, 'lifecycle': lifecycle,
        'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--scratch', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.source, args.scratch, args.output)
    put(Path(args.output) / f'{args.case}-physical-preparation.json', result)
    print(json.dumps({'case_id': args.case, 'fixtures_passed': 3,
                      'physical_or_legal_acceptance_claimed': False}))
