"""Source-shaped physical and ownership protocol tests, explicitly diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c376609-owner-nov26/physical-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def setup():
    output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if (ROOT / '.runtime-work').resolve() not in output.parents:
        raise ValueError('private runtime output root required before direct import')
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    return physical_result, seal_capture, record_native_exit, acknowledge_owner_release


def physical(config, suffix, kind, physical_result):
    root = SCRATCH / suffix / kind
    root.mkdir(parents=True, exist_ok=False)
    write(root / 'config.json', config)
    if kind != 'missing':
        progress = 200 if kind == 'complete' else 1
        rows = [{'frame': 100 + i, 'time_s': i / 20,
                 'position_m': [progress * i / 899, 0]} for i in range(900)]
        (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        mapping = [{'video_frame': i, 'carla_frame': 100 + i,
                    'native_frame': 100 + i, 'time_s': i / 20} for i in range(900)]
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
    result = {'case_id': config['selected_case_id'], 'measured_values': {}, 'target_checks': [],
              'recording_description': config['case']['recording_description'],
              'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl', 'recording_evidence': [],
              'physical_failure_flags': {'diagnostic_fixture': True}}
    assessed = physical_result(root, result)
    status = assessed['physical_checks']['maneuver']['status']
    expected = {'complete': 'met', 'incomplete': 'not_met', 'missing': 'unverified'}[kind]
    if status != expected or assessed.get('diagnostic_fixture') is not True or assessed.get('physical_acceptance_claimed') is not False:
        raise ValueError('source-shaped physical outcome did not separate ' + kind)
    result_path = HERE / 'proofs' / 'physical' / suffix / (kind + '-result.json')
    log_path = HERE / 'proofs' / 'physical' / suffix / (kind + '.log')
    write(result_path, assessed)
    log_path.write_text('case ' + config['selected_case_id'] + '\nkind ' + kind +
                        '\nobserved maneuver ' + status +
                        '\nprovenance synthetic_fixture; diagnostic_fixture true\n')
    return {'kind': {'complete': 'complete_motion', 'incomplete': 'incomplete_motion',
                     'missing': 'missing_evidence'}[kind],
            'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + HERE.name + '/prove_physical.py',
            'exit_code': 0, 'log': str(log_path.relative_to(HERE)), 'log_sha256': sha(log_path),
            'result': str(result_path.relative_to(HERE)), 'result_sha256': sha(result_path)}


def lifecycle(case, suffix, seal_capture, record_native_exit, acknowledge_owner_release):
    root = SCRATCH / suffix / 'lifecycle'
    root.mkdir(parents=True, exist_ok=False)
    write(root / 'config.json', {'selected_case_id': case})
    write(root / 'construction.json', {'case_id': case})
    (root / 'runner.py').write_text('# synthetic ownership protocol only\n')
    (root / 'trace.jsonl').write_text('{"frame":100,"time_s":0}\n')
    (root / 'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":100,"time_s":0}\n')
    write(root / 'acquisition-provenance.json', {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    seal_capture(root, frames=1, restoration={'restored': True}, errors=[], encoder_exit_codes={'overview': 0})
    record_native_exit(root)
    receipt = acknowledge_owner_release(root, root / 'owner-release.json', True)
    if receipt.get('event') != 'owner_released':
        raise ValueError('owner release did not follow sealed Native exit')
    saved = json.loads((HERE / ('proof-saved-primary-' + suffix + '.log')).read_text())
    if not (saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True):
        raise ValueError('saved replay proof absent')
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    log = HERE / 'proofs' / 'physical' / suffix / 'lifecycle.log'
    log.write_text('case ' + case + '\n' + '\n'.join(events) +
                   '\nsynthetic lifecycle and recorded-only replay\n')
    return {'events': events, 'exit_code': 0, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log)}


def run():
    physical_result, seal_capture, record_native_exit, acknowledge_owner_release = setup()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    receipts = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
        outcomes = [physical(config, suffix, kind, physical_result) for kind in ('complete', 'incomplete', 'missing')]
        life = lifecycle(entry['case_id'], suffix, seal_capture, record_native_exit, acknowledge_owner_release)
        receipt = {'format': 'turn-lane-source-shaped-physical-protocol', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'], 'fixtures': outcomes,
                   'lifecycle': life, 'original_source_verified': False,
                   'physical_acceptance_claimed': False, 'legal_verdict': None}
        target = HERE / ('physical-' + suffix + '-receipt.json')
        write(target, receipt)
        receipts.append(target.name + ' ' + sha(target))
    (HERE / 'proof-physical-lifecycle.log').write_text('\n'.join(receipts) + '\n')
    return len(receipts)


if __name__ == '__main__':
    print('source-shaped physical and lifecycle cases:', run())
