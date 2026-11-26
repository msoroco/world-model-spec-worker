"""Three source-shaped physical outcomes and Native ownership lifecycle checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c229628-physical-v2'
PROOFS = HERE / 'proofs/physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.is_relative_to(HERE) and path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('physical proof exceeds return size')


def runtime():
    output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    private = (ROOT / '.runtime-work').resolve()
    if output != private and private not in output.parents:
        raise ValueError('export private output root before direct runtime import')
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))


def outcome(config, suffix, kind):
    from worker_exchange.native_output import physical_result
    root = SCRATCH / suffix / kind
    if root.exists():
        raise ValueError('retain prior physical source fixture')
    root.mkdir(parents=True)
    write(root / 'config.json', config)
    mapping = [{'video_frame': i, 'carla_frame': 100 + i,
                'native_frame': 100 + i, 'time_s': i / 20} for i in range(900)]
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
    if kind != 'missing_evidence':
        progress = 200 if kind == 'complete_motion' else 1
        trace = [{'frame': 100 + i, 'time_s': i / 20,
                  'position_m': [progress * i / 899, 0, 0]} for i in range(900)]
        (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    target = {'target': 'original sampled two-vehicle route progress',
              'requested': 'finite original motion', 'measured': kind,
              'method': 'source-shaped 900-frame CPU motion fixture',
              'tolerance': 0, 'matched': kind == 'complete_motion',
              'physical_cause_confirmed': False,
              'cause_evidence': {'config.json': sha(root / 'config.json')}}
    result = {'case_id': config['selected_case_id'], 'target_checks': [target],
              'measured_values': {},
              'recording_description': config['case']['recording_description'],
              'trace_reference': 'trace.jsonl', 'video_references': ['overview.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_evidence': [], 'realized_observables': {},
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'CPU physical fixture only',
              'physical_failure_flags': ['synthetic_fixture']}
    result = physical_result(root, result)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    actual = result['physical_checks']['maneuver']['status']
    if actual != expected:
        raise ValueError('physical outcome mismatch: ' + kind + ' ' + actual)
    target = PROOFS / suffix / (kind + '-result.json')
    write(target, result)
    log = PROOFS / suffix / (kind + '.log')
    log.write_text('case ' + config['selected_case_id'] + '\nkind ' + kind +
                   '\nobserved maneuver ' + actual +
                   '\nprovenance synthetic_fixture; diagnostic_fixture true\n')
    return {'kind': kind, 'command':
            'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c229628-output .venv-cpu/bin/python work/' + HERE.name + '/prove_physical.py --all',
            'exit_code': 0, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'result': str(target.relative_to(HERE)),
            'result_sha256': sha(target)}


def lifecycle(config, suffix):
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit
    root = SCRATCH / suffix / 'lifecycle'
    if root.exists():
        raise ValueError('retain prior lifecycle fixture')
    root.mkdir(parents=True)
    write(root / 'construction.json', {'case_id': config['selected_case_id']})
    (root / 'runner.py').write_text('# source-shaped lifecycle fixture\n')
    (root / 'trace.jsonl').write_text('{"frame":100,"time_s":0.0}\n')
    (root / 'video_frames.jsonl').write_text(
        '{"video_frame":0,"carla_frame":100,"native_frame":100,"time_s":0.0}\n')
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    seal_capture(root, frames=1, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={'overview': 0})
    record_native_exit(root)
    owner = acknowledge_owner_release(root, root / 'owner-release.json', True)
    saved = json.loads((HERE / ('proof-selected-saved-' + suffix + '.log')).read_text())
    if not (owner['event'] == 'owner_released' and saved.get('passed') is True and
            saved.get('recorded_only') is True and saved.get('originals_preserved') is True):
        raise ValueError('lifecycle or saved replay proof incomplete')
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    log = PROOFS / suffix / 'lifecycle.log'
    log.write_text('case ' + config['selected_case_id'] + '\n' +
                   '\n'.join(events) + '\nsynthetic lifecycle and saved replay\n')
    return {'events': events, 'exit_code': 0,
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}


def run():
    runtime()
    manifest = json.loads((HERE / 'execution-manifest.selected-draft.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        fixtures = [outcome(config, suffix, kind) for kind in
                    ('complete_motion', 'incomplete_motion', 'missing_evidence')]
        life = lifecycle(config, suffix)
        write(HERE / ('physical-' + suffix + '-receipt.json'), {
            'format': 'contest-aid-physical-preparation',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'fixtures': fixtures, 'lifecycle': life,
            'physical_acceptance_claimed': False, 'legal_verdict': None})
    return len(manifest['cases'])


if __name__ == '__main__':
    argparse.ArgumentParser().add_argument('--all', action='store_true', required=True)
    print('physical case proofs:', run())
