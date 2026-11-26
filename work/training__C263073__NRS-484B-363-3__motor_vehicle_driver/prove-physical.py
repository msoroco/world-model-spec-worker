"""Exercise source-bound physical status and capture ordering with CPU fixtures."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from native.branch_cases import CASES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prove(suffix):
    case = HERE.name + '__' + suffix
    construction_path = HERE / 'native/bundles' / suffix / 'construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    source = HERE / 'diagnostic-source' / suffix
    output = HERE / 'proofs' / suffix
    output.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work/c263073-owner', prefix='physical-') as temporary:
        root = Path(temporary)
        write(root / 'config.json', config)
        for name in ('native-motion.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'school-context.json'):
            shutil.copyfile(source / name, root / name)
        original = (root / 'native-motion.jsonl').read_text()
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            path = root / 'native-motion.jsonl'
            if kind == 'complete_motion':
                path.write_text(original)
            elif kind == 'incomplete_motion':
                rows = [json.loads(line) for line in original.splitlines()]
                start = rows[0]['ego']['center_xy_m']
                body = rows[0]['ego']['body_xy_m']
                for row in rows:
                    row['ego']['center_xy_m'] = start
                    row['ego']['body_xy_m'] = body
                    row['ego']['heading_deg'] = rows[0]['ego']['heading_deg']
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            else:
                path.unlink()
            assessed = assess_physical(root, config)
            status = assessed['physical_checks']['maneuver']['status']
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError(f'{suffix} {kind}: {status} != {expected}')
            result = {'case_id': case, 'physical_checks': assessed['physical_checks'],
                      'maneuver_completed': status == 'met',
                      'realized_observables': assessed['realized_observables'] if status == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            result_path = output / ('physical-' + kind + '-result.json')
            log_path = output / ('physical-' + kind + '.log')
            write(result_path, result)
            write(log_path, {'kind': kind, 'observed': status, 'expected': expected})
            fixtures.append({'kind': kind, 'command': 'prove-physical.py ' + suffix,
                             'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                             'log_sha256': sha(log_path),
                             'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        closure = root / 'closure'
        closure.mkdir()
        for name, value in (('config.json', json.dumps(config)),
                            ('runner.py', 'synthetic runner'),
                            ('trace.jsonl', (source / 'trace.jsonl').read_text()),
                            ('video_frames.jsonl', (source / 'video_frames.jsonl').read_text()),
                            ('construction.json', json.dumps(construction))):
            (closure / name).write_text(value)
        write(closure / 'acquisition-provenance.json', {'diagnostic_fixture': True})
        seal = seal_capture(closure, frames=600, restoration={'restored': True},
                            errors=[], encoder_exit_codes={'overview': 0})
        exit_receipt = record_native_exit(closure)
        owner = acknowledge_owner_release(closure, root / 'owner-release.json', True)
        events = seal['events'] + [exit_receipt['event'], owner['event'], 'saved_processing_started']
        expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected_events:
            raise ValueError('Closure event order differs')
        life_log = output / 'physical-lifecycle.log'
        write(life_log, {'events': events, 'seal_sha256': sha(closure / 'capture-seal.json'),
                         'native_exit_sha256': sha(closure / 'native-exit.json'),
                         'owner_release_sha256': sha(root / 'owner-release.json')})
    proof = output / 'physical-preparation.json'
    write(proof, {'format': 'c263073-physical-preparation-cpu-proof-v1',
                  'case_id': case, 'construction_sha256': sha(construction_path),
                  'fixtures': fixtures,
                  'lifecycle': {'events': expected_events, 'exit_code': 0,
                                'log': str(life_log.relative_to(HERE)),
                                'log_sha256': sha(life_log)},
                  'original_native_executed': False})
    return {'case_id': case, 'receipt': str(proof.relative_to(HERE)), 'sha256': sha(proof)}


if __name__ == '__main__':
    print(json.dumps([prove(s) for s in CASES]))
