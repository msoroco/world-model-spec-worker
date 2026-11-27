"""Three synthetic lane-transition outcomes and ordered lifecycle CPU proof."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prove(entry):
    from worker_exchange.native_output import physical_result
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    source = REPO / '.runtime-work' / ('c245490_compat_v7_' + suffix)
    scratch = REPO / '.runtime-work' / ('c245490_physical_' + suffix)
    output = HERE / 'physical-proof' / suffix
    if scratch.exists():
        raise ValueError('Physical scratch must be fresh: ' + suffix)
    scratch.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((source / 'result.json').read_text())
    motion = [json.loads(line) for line in (source / 'body_history.jsonl').read_text().splitlines()]
    fixtures = []
    for kind, expected in (('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        attempt = scratch / kind
        attempt.mkdir()
        for name in ('config.json', 'video_frames.jsonl', 'trace.jsonl',
                     'acquisition-provenance.json'):
            shutil.copyfile(source / name, attempt / name)
        if kind != 'missing_evidence':
            rows = motion if kind == 'complete_motion' else [
                dict(row, lane_id=motion[0]['lane_id']) for row in motion]
            (attempt / 'body_history.jsonl').write_text(''.join(
                json.dumps(row, allow_nan=False) + '\n' for row in rows))
        result = physical_result(attempt, dict(baseline))
        actual = result['physical_checks']['maneuver']['status']
        if actual != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError('Physical classification differs: ' + suffix + ' ' + kind + ' ' + actual)
        if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
            raise ValueError('Synthetic provenance lost')
        result_path = output / (kind + '.json')
        log_path = output / (kind + '.log')
        put(result_path, result)
        log_path.write_text(kind + ': ' + actual + '; synthetic physical diagnostic only\n')
        fixtures.append({'kind': kind, 'command': 'prove_physical.py --case ' + entry['case_id'] + ' --fixture ' + kind,
                         'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                         'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                         'result_sha256': sha(result_path)})
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    if events.index('saved_processing_started') <= events.index('owner_released'):
        raise ValueError('Lifecycle order')
    life_log = output / 'lifecycle.log'
    life_log.write_text('Synthetic lifecycle ordering accepted; early saved processing rejected\n')
    lifecycle = {'events': events, 'exit_code': 0,
                 'log': str(life_log.relative_to(HERE)), 'log_sha256': sha(life_log),
                 'synthetic_fixture': True, 'actual_owner_release_claimed': False}
    receipt = {'format': 'worker-signal-lane-physical-preparation',
               'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
               'fixtures': fixtures, 'lifecycle': lifecycle,
               'physical_or_legal_acceptance_claimed': False}
    path = output / 'proof.json'
    put(path, receipt)
    return {'case_id': entry['case_id'], 'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)}


def main():
    manifest = json.loads((HERE / 'draft-native-manifest.json').read_text())
    return [prove(entry) for entry in manifest['cases']]


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
