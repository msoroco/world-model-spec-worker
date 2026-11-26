"""Prove the source-bound motion and Native closure checkers with CPU fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def prove(number, behavior):
    case = f'{HERE.name}__controlled_{number}'
    construction_path = HERE / f'draft-mounted-sidewalk/{behavior}/primary/construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    source = HERE / 'diagnostic-source' / behavior
    original_trace = (source / 'trace.jsonl').read_text()
    original_map = (source / 'video_frames.jsonl').read_text()
    destination = HERE / 'physical-preparation' / f'controlled_{number}'
    destination.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c230207-physical-') as temporary:
        root = Path(temporary)
        write(root / 'config.json', config)
        (root / 'video_frames.jsonl').write_text(original_map)
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            trace = root / 'trace.jsonl'
            if kind == 'complete_motion':
                trace.write_text(original_trace)
            elif kind == 'incomplete_motion':
                rows = [json.loads(line) for line in original_trace.splitlines()]
                initial = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = initial
                    row['position'] = {'x': initial[0], 'y': initial[1], 'z': initial[2]}
                trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            else:
                trace.unlink()
            assessed = assess_physical(root, config)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            status = assessed['physical_checks']['maneuver']['status']
            if status != expected:
                raise ValueError(f'{kind}: {status} differs from {expected}')
            result = {'case_id': case, 'physical_checks': assessed['physical_checks'],
                      'maneuver_completed': status == 'met',
                      'realized_observables': assessed['realized_observables'] if status == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            result_path = destination / (kind + '.json')
            log_path = destination / (kind + '.log')
            write(result_path, result)
            write(log_path, {'kind': kind, 'observed': status, 'expected': expected})
            fixtures.append({'kind': kind, 'command': 'prove-physical.py --case ' + case,
                             'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                             'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        closure = root / 'closure'
        closure.mkdir()
        for name, data in (('config.json', json.dumps(config)), ('runner.py', 'synthetic runner'),
                           ('trace.jsonl', original_trace), ('video_frames.jsonl', original_map),
                           ('construction.json', json.dumps(construction))):
            (closure / name).write_text(data)
        write(closure / 'acquisition-provenance.json', {'diagnostic_fixture': True})
        seal = seal_capture(closure, frames=600, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'overview': 0})
        native_exit = record_native_exit(closure)
        owner = acknowledge_owner_release(closure, root / 'owner-release.json', True)
        events = seal['events'] + [native_exit['event'], owner['event'], 'saved_processing_started']
        expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected_events:
            raise ValueError('Native lifecycle event order differs')
        life_log = destination / 'lifecycle.log'
        write(life_log, {'events': events, 'seal_sha256': sha(closure / 'capture-seal.json'),
                         'native_exit_sha256': sha(closure / 'native-exit.json'),
                         'owner_release_sha256': sha(root / 'owner-release.json')})
    proof_path = destination / 'physical-preparation.json'
    write(proof_path, {'format': 'c230207-physical-preparation-cpu-proof-v1',
                       'case_id': case, 'construction_sha256': sha(construction_path),
                       'fixtures': fixtures,
                       'lifecycle': {'events': expected_events, 'exit_code': 0,
                                     'log': str(life_log.relative_to(HERE)),
                                     'log_sha256': sha(life_log)},
                       'original_native_executed': False})
    return {'case_id': case, 'proof_sha256': sha(proof_path)}


if __name__ == '__main__':
    print(json.dumps([prove(1, 'walk_cycle'), prove(2, 'mounted_sidewalk')], sort_keys=True))
