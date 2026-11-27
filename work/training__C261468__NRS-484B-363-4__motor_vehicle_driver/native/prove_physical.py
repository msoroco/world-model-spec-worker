"""Independent CPU motion and capture-order diagnostics for selected cases."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def ordered_lifecycle(events):
    expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                'native_exit', 'owner_released', 'saved_processing_started']
    if events != expected:
        raise ValueError('Saved processing precedes Native ownership closure')
    return expected


def prove(case, source, scratch, output):
    from worker_exchange.native_output import physical_result
    source, scratch, output = map(lambda x: Path(x).resolve(), (source, scratch, output))
    if scratch.exists():
        raise ValueError('Use fresh CPU scratch')
    scratch.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).resolve().parents[1]
    slug = case.rsplit('__', 1)[-1]
    config = package / 'native' / 'planned-configs' / (slug + '.json')
    original = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
    fixtures = []
    for kind, expected in [('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')]:
        attempt = scratch / kind
        attempt.mkdir()
        shutil.copyfile(config, attempt / 'config.json')
        shutil.copyfile(source / 'video_frames.jsonl', attempt / 'video_frames.jsonl')
        if kind != 'missing_evidence':
            rows = json.loads(json.dumps(original))
            if kind == 'incomplete_motion':
                first = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = first
                    row['position'] = rows[0]['position']
                    row['speed_mps'] = 0
            (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = physical_result(attempt, {'target_checks': []})
        status = result['physical_checks']['maneuver']['status']
        if status != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError(kind + ': expected ' + expected + ', got ' + status)
        if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
            raise ValueError('Synthetic diagnostic provenance lost')
        result_path = output / ('cpu-' + slug + '-' + kind + '-result.json')
        log_path = output / ('cpu-' + slug + '-' + kind + '.log')
        write(result_path, result)
        log_path.write_text(kind + ': ' + status + '; source-bound CPU diagnostic only\n')
        fixtures.append({'kind': kind, 'command': 'native/prove_physical.py --case ' + case + ' --fixture ' + kind,
                         'exit_code': 0, 'log': str(log_path.relative_to(package)),
                         'log_sha256': sha(log_path), 'result': str(result_path.relative_to(package)),
                         'result_sha256': sha(result_path)})
    events = ordered_lifecycle(['capture_finished', 'encoders_closed', 'restoration_verified',
                                'native_exit', 'owner_released', 'saved_processing_started'])
    try:
        ordered_lifecycle(events[:-2] + ['saved_processing_started'])
    except ValueError as error:
        if 'precedes Native ownership closure' not in str(error):
            raise
    else:
        raise ValueError('Premature saved processing was accepted')
    life_log = output / ('cpu-' + slug + '-lifecycle.log')
    life_log.write_text('Complete source ownership order accepted; early saved processing rejected\n')
    proof = {'format': 'c261468-physical-preparation-v1', 'case_id': case,
             'construction_sha256': sha(package / 'native' / 'selected-native-draft' / slug / 'construction.json'),
             'fixtures': fixtures,
             'lifecycle': {'events': events, 'exit_code': 0, 'log': str(life_log.relative_to(package)),
                           'log_sha256': sha(life_log), 'synthetic_fixture': True,
                           'actual_owner_release_claimed': False},
             'physical_or_legal_acceptance_claimed': False}
    receipt_path = output / ('cpu-' + slug + '-physical-preparation.json')
    write(receipt_path, proof)
    return receipt_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('case', 'source', 'scratch', 'output'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    print(prove(args.case, args.source, args.scratch, args.output))
