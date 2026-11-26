"""CPU exercise of right-pass completion and saved processing ownership checks."""
import hashlib
import os
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO/'.runtime-work'/'c146314-3-physical')
sys.path.insert(0, str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n' for row in rows)


def run_case(probe):
    case = HERE.name+'__'+probe
    construction_path = HERE/'native'/(probe+'-construction.json')
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    source = HERE/'native/diagnostic'/probe/'sources'
    destination = HERE/'native/proofs'/probe
    destination.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work', prefix='c230259-physical-') as temporary:
        root = Path(temporary)
        (root/'config.json').write_text(json.dumps(config))
        (root/'video_frames.jsonl').write_bytes((source/'video_frames.jsonl').read_bytes())
        original_trace = (source/'trace.jsonl').read_text()
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            trace_path = root/'trace.jsonl'
            if kind == 'missing_evidence':
                trace_path.unlink(missing_ok=True)
            elif kind == 'incomplete_motion':
                rows = [json.loads(line) for line in original_trace.splitlines()]
                start = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = start
                trace_path.write_text(lines(rows))
            else:
                trace_path.write_text(original_trace)
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
            result_path = destination/('physical-'+kind+'-result.json')
            log_path = destination/('physical-'+kind+'.log')
            write(result_path, result)
            write(log_path, {'kind': kind, 'expected': expected, 'observed': actual,
                             'source_present': trace_path.is_file()})
            fixtures.append({'kind': kind, 'command': 'prove_physical.py --case '+case,
                             'exit_code': 0, 'log': str(log_path.relative_to(HERE)),
                             'log_sha256': sha(log_path), 'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        lifecycle = root/'lifecycle'
        lifecycle.mkdir()
        for name, value in [('config.json', json.dumps(config)), ('runner.py', 'synthetic runner'),
                            ('trace.jsonl', original_trace),
                            ('video_frames.jsonl', (source/'video_frames.jsonl').read_text()),
                            ('construction.json', json.dumps(construction))]:
            (lifecycle/name).write_text(value)
        write(lifecycle/'acquisition-provenance.json', {'diagnostic_fixture': True})
        seal = seal_capture(lifecycle, frames=600, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'overview': 0})
        exit_record = record_native_exit(lifecycle)
        owner = acknowledge_owner_release(lifecycle, root/'owner-release.json', True)
        events = seal['events']+[exit_record['event'], owner['event'], 'saved_processing_started']
        expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected_events:
            raise ValueError('Capture lifecycle order differs')
        lifecycle_log = destination/'physical-lifecycle.log'
        write(lifecycle_log, {'events': events, 'seal_sha256': sha(lifecycle/'capture-seal.json'),
                              'native_exit_sha256': sha(lifecycle/'native-exit.json'),
                              'owner_release_sha256': sha(root/'owner-release.json')})
    proof_path = destination/'physical-preparation.json'
    write(proof_path, {'format': 'c146314-3-physical-preparation-cpu-proof-v1',
                       'case_id': case, 'construction_sha256': sha(construction_path),
                       'fixtures': fixtures, 'lifecycle': {'events': expected_events,
                           'exit_code': 0, 'log': str(lifecycle_log.relative_to(HERE)),
                           'log_sha256': sha(lifecycle_log)},
                       'original_native_executed': False})
    return {'case_id': case, 'receipt': str(proof_path.relative_to(HERE)), 'sha256': sha(proof_path)}


if __name__ == '__main__':
    print(json.dumps({'proofs': [run_case(probe) for probe in ('probe_a','probe_b')]}, indent=2))
