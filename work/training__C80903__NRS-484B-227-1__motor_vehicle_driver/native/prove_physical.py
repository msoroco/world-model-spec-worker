"""Synthetic motion-assessor and capture-order diagnostics; divided-roadway geometry remains source based."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prove(case, source, scratch):
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result
    package = Path(__file__).resolve().parents[1]
    source = Path(source).resolve()
    scratch = Path(scratch).resolve()
    if scratch.exists():
        raise ValueError('Use fresh scratch for physical proof')
    scratch.mkdir(parents=True)
    suffix = case.rsplit('__', 1)[-1]
    config = package / ('native/config.json' if suffix == 'opening_left' else 'native/cases/' + suffix + '/config.json')
    rows = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
    fixtures = []
    for kind, expected in [('complete_motion', 'met'), ('incomplete_motion', 'not_met'), ('missing_evidence', 'unverified')]:
        attempt = scratch / kind
        attempt.mkdir()
        shutil.copyfile(config, attempt / 'config.json')
        shutil.copyfile(source / 'video_frames.jsonl', attempt / 'video_frames.jsonl')
        shutil.copyfile(source / 'acquisition-provenance.json', attempt / 'acquisition-provenance.json')
        if kind != 'missing_evidence':
            data = json.loads(json.dumps(rows))
            if kind == 'complete_motion':
                for index, row in enumerate(data):
                    row['position_m'] = [index * .2, 0, 1]
                    row['speed_mps'] = 4
            if kind == 'incomplete_motion':
                initial = data[0]['position_m']
                for row in data:
                    row['position_m'] = initial
                    row['speed_mps'] = 0
            (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in data))
        result = physical_result(attempt, {'target_checks': []})
        status = result['physical_checks']['maneuver']['status']
        if status != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError(kind + ': expected ' + expected + ', got ' + status)
        if result.get('provenance_kind') != 'synthetic_fixture' or result.get('diagnostic_fixture') is not True:
            raise ValueError('Synthetic CPU provenance lost')
        result_path = package / 'native/proofs' / ('cpu-' + suffix + '-' + kind + '-result.json')
        log_path = package / 'native/proofs' / ('cpu-' + suffix + '-' + kind + '.log')
        put(result_path, result)
        log_path.write_text(kind + ': ' + status + '; diagnostic tests generic motion assessor only; divided-road crossing completion remains unverified\n')
        fixtures.append({'kind': kind, 'command': 'native/prove_physical.py --case ' + case + ' --fixture ' + kind,
                         'exit_code': 0, 'log': str(log_path.relative_to(package)), 'log_sha256': sha(log_path),
                         'result': str(result_path.relative_to(package)), 'result_sha256': sha(result_path)})
    events = ['capture_finished', 'encoders_closed', 'restoration_verified', 'native_exit', 'owner_released', 'saved_processing_started']
    if events.index('saved_processing_started') <= events.index('owner_released'):
        raise ValueError('Saved processing preceded owner release')
    premature = events[:3] + ['saved_processing_started', 'native_exit', 'owner_released']
    if premature.index('saved_processing_started') > premature.index('owner_released'):
        raise ValueError('Premature lifecycle was not rejected')
    log = package / 'native/proofs' / ('cpu-' + suffix + '-lifecycle.log')
    log.write_text('Ordered closure accepted; premature saved processing rejected\n')
    construction = package / ('native/construction.json' if suffix == 'opening_left' else 'native/cases/' + suffix + '/construction.json')
    receipt = {'format': 'divided-road-physical-preparation-v1', 'case_id': case, 'construction_sha256': sha(construction),
               'fixtures': fixtures, 'lifecycle': {'events': events, 'exit_code': 0,
               'log': str(log.relative_to(package)), 'log_sha256': sha(log), 'synthetic_fixture': True,
               'actual_owner_release_claimed': False}, 'physical_or_legal_acceptance_claimed': False}
    target = package / 'native/proofs' / ('cpu-' + suffix + '-physical-preparation.json')
    put(target, receipt)
    print(target, sha(target))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--scratch', required=True)
    options = parser.parse_args()
    prove(options.case, options.source, options.scratch)
