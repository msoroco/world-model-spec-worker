"""Exercise original-motion assessment and closure on small software fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n' for value in values)


def run_case(suffix):
    case = HERE.name + '__' + suffix
    construction_path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    diagnostic = json.loads((HERE / ('diagnostic-' + suffix + '.json')).read_text())
    destination = HERE / 'proofs' / suffix
    destination.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c230231-physical-') as temporary:
        root = Path(temporary)
        (root / 'config.json').write_text(json.dumps(config))
        (root / 'video_frames.jsonl').write_text(diagnostic['files']['video_frames.jsonl'])
        (root / 'trace.jsonl').write_text(diagnostic['files']['trace.jsonl'])
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            source = root / 'trace.jsonl'
            if kind == 'incomplete_motion':
                trace = rows(diagnostic['files']['trace.jsonl'])
                start = trace[0]['position_m']
                for row in trace:
                    row['position_m'] = start
                source.write_text(lines(trace))
            if kind == 'missing_evidence':
                source.unlink()
            assessment = assess_physical(root, config)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            actual = assessment['physical_checks']['maneuver']['status']
            if actual != expected:
                raise ValueError(f'{kind} physical assessment {actual} != {expected}')
            result = {'case_id': case, 'physical_checks': assessment['physical_checks'],
                      'maneuver_completed': actual == 'met',
                      'realized_observables': assessment['realized_observables'] if actual == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            result_path = destination / ('physical-' + kind + '-result.json')
            log_path = destination / ('physical-' + kind + '.log')
            write(result_path, result)
            write(log_path, {'kind': kind, 'expected': expected, 'observed': actual,
                             'source_present': source.is_file()})
            fixtures.append({'kind': kind, 'command': 'prove-physical.py --case ' + case,
                'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                'result_sha256': sha(result_path)})
            if not source.is_file():
                source.write_text(diagnostic['files']['trace.jsonl'])
        lifecycle = root / 'lifecycle'
        lifecycle.mkdir()
        for name, value in [('config.json', json.dumps(config)), ('runner.py', 'synthetic runner'),
                            ('trace.jsonl', diagnostic['files']['trace.jsonl']),
                            ('video_frames.jsonl', diagnostic['files']['video_frames.jsonl']),
                            ('construction.json', json.dumps(construction))]:
            (lifecycle / name).write_text(value)
        write(lifecycle / 'acquisition-provenance.json', {'diagnostic_fixture': True})
        seal = seal_capture(lifecycle, frames=600, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'overview': 0})
        exit_record = record_native_exit(lifecycle)
        owner = acknowledge_owner_release(lifecycle, root / 'owner-release.json', True)
        events = seal['events'] + [exit_record['event'], owner['event'], 'saved_processing_started']
        expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected_events:
            raise ValueError('Capture lifecycle order differs')
        lifecycle_log = destination / 'physical-lifecycle.log'
        write(lifecycle_log, {'events': events, 'seal_sha256': sha(lifecycle / 'capture-seal.json'),
                              'native_exit_sha256': sha(lifecycle / 'native-exit.json'),
                              'owner_release_sha256': sha(root / 'owner-release.json')})
    proof_path = destination / 'physical-preparation.json'
    write(proof_path, {'format': 'c230231-physical-preparation-cpu-proof-v1',
                       'case_id': case, 'construction_sha256': sha(construction_path),
                       'fixtures': fixtures, 'lifecycle': {'events': expected_events,
                           'exit_code': 0, 'log': str(lifecycle_log.relative_to(HERE)),
                           'log_sha256': sha(lifecycle_log)},
                       'original_native_executed': False})
    return {'case_id': case, 'receipt': str(proof_path.relative_to(HERE)),
            'sha256': sha(proof_path)}


if __name__ == '__main__':
    print(json.dumps({'proofs': [run_case(s) for s in
        ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')]}, indent=2))
