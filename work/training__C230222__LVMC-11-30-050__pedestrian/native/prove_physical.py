"""Three synthetic physical outcomes and capture ownership lifecycle order."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from finalize import physical_completion


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    for suffix in ('a', 'b'):
        construction = ROOT / 'selected' / ('condition_' + suffix) / 'primary/construction.json'
        case_id = json.loads(construction.read_text())['case_id']
        folder = ROOT / 'physical-proof' / ('condition_' + suffix)
        value = {'source_kind': 'native_observation', 'frames': 600,
                 'entry_distance_to_origin_curb_m': .05,
                 'exit_distance_to_opposite_curb_m': .08,
                 'route_length_m': 7.1, 'shortest_to_opposite_curb_m': 7.0}
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            current = copy.deepcopy(value)
            joined = {'frames': 600}
            if kind == 'incomplete_motion':
                current['exit_distance_to_opposite_curb_m'] = 1.8
            if kind == 'missing_evidence':
                joined = None
            completion = physical_completion(current, joined, original_reviewed=True)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if completion['physical_checks']['maneuver']['status'] != expected:
                raise AssertionError('Physical completion branch differs')
            result = {**completion, 'provenance_kind': 'synthetic_fixture',
                      'diagnostic_fixture': True, 'realized_observables':
                          {'entry_exit_source_distance_m': current['exit_distance_to_opposite_curb_m']}
                          if kind == 'complete_motion' else {},
                      'accepted': False, 'legal_verdict_claimed': False}
            result_path, log_path = folder / (kind + '.json'), folder / (kind + '.log')
            write(result_path, result)
            log_path.write_text('Synthetic physical checker outcome: ' + expected + '\n')
            fixtures.append({'kind': kind, 'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                             'work/' + ROOT.name + '/native/prove_physical.py',
                             'exit_code': 0, 'log': str(log_path.relative_to(ROOT)),
                             'log_sha256': sha(log_path), 'result': str(result_path.relative_to(ROOT)),
                             'result_sha256': sha(result_path)})
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        if events.index('saved_processing_started') <= events.index('owner_released'):
            raise AssertionError('Saved processing began before release')
        lifecycle_log = folder / 'lifecycle.log'
        lifecycle_log.write_text('\n'.join(events) + '\n')
        proof = {'format': 'worker-physical-preparation-proof-v1', 'case_id': case_id,
                 'construction_sha256': sha(construction), 'fixtures': fixtures,
                 'lifecycle': {'events': events, 'exit_code': 0,
                               'log': str(lifecycle_log.relative_to(ROOT)),
                               'log_sha256': sha(lifecycle_log)},
                 'original_native_observed': False}
        output = folder / 'proof.json'
        write(output, proof)
        print(json.dumps({'case_id': case_id, 'proof': str(output), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
