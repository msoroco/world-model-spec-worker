"""Exercise original motion completion and Native ownership order on CPU fixtures."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(ROOT / '.runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run_case(suffix):
    case = HERE.name + '__' + suffix
    construction_path = HERE / 'draft-bridge' / ('below_posted_structure_speed' if suffix == 'probe_01' else 'above_posted_structure_speed') / 'primary/construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    source = ROOT / '.runtime-work' / ('c32014-saved-fixture-' + suffix[-2:])
    if not (source / 'trace.jsonl').is_file():
        raise ValueError('Materialize the exact fixture recipe under .runtime-work first')
    destination = HERE / 'proof' / suffix
    fixtures = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c32014-physical-') as temporary:
        root = Path(temporary)
        (root / 'config.json').write_text(json.dumps(config) + '\n')
        (root / 'video_frames.jsonl').write_bytes((source / 'video_frames.jsonl').read_bytes())
        original_trace = (source / 'trace.jsonl').read_text()
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            trace_path = root / 'trace.jsonl'
            if kind == 'missing_evidence':
                trace_path.unlink(missing_ok=True)
            elif kind == 'incomplete_motion':
                rows = [json.loads(line) for line in original_trace.splitlines()]
                start = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = start
                    row['position'] = {'x': start[0], 'y': start[1], 'z': start[2]}
                trace_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            else:
                trace_path.write_text(original_trace)
            assessment = assess_physical(root, config)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            observed = assessment['physical_checks']['maneuver']['status']
            if observed != expected:
                raise ValueError(f'{kind} physical assessment {observed} != {expected}')
            result = {'case_id': case, 'physical_checks': assessment['physical_checks'],
                      'maneuver_completed': observed == 'met',
                      'realized_observables': assessment['realized_observables'] if observed == 'met' else {},
                      'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
            result_path = destination / ('physical-' + kind + '-result.json')
            log_path = destination / ('physical-' + kind + '.log')
            write(result_path, result)
            write(log_path, {'kind': kind, 'expected': expected, 'observed': observed,
                             'source_present': trace_path.is_file()})
            fixtures.append({'kind': kind, 'command': 'prove_physical.py --case ' + case,
                             'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                             'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        lifecycle = root / 'lifecycle'
        lifecycle.mkdir()
        for name, value in [('config.json', json.dumps(config)), ('runner.py', 'synthetic runner'),
                            ('trace.jsonl', original_trace),
                            ('video_frames.jsonl', (source / 'video_frames.jsonl').read_text()),
                            ('construction.json', json.dumps(construction))]:
            (lifecycle / name).write_text(value)
        write(lifecycle / 'acquisition-provenance.json', {'diagnostic_fixture': True})
        seal = seal_capture(lifecycle, frames=600, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'overview': 0, 'approach': 0,
                                                'reference_corner': 0, 'driver_reference': 0})
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
    write(proof_path, {'format': 'c32014-physical-preparation-cpu-proof-v1',
                       'case_id': case, 'construction_sha256': sha(construction_path),
                       'fixtures': fixtures, 'lifecycle': {'events': expected_events,
                           'exit_code': 0, 'log': str(lifecycle_log.relative_to(HERE)),
                           'log_sha256': sha(lifecycle_log)},
                       'original_native_executed': False})
    return {'case_id': case, 'receipt': str(proof_path.relative_to(HERE)), 'sha256': sha(proof_path)}


if __name__ == '__main__':
    print(json.dumps({'proofs': [run_case(suffix) for suffix in ('probe_01', 'probe_02')]}, indent=2))
