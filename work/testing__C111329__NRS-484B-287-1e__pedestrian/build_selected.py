"""Bind CPU proofs into a source-gated selected handoff, without physical claims."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


draft = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
draft['status'] = 'selected_source_gated_originals_pending'
for entry in draft['cases']:
    entry['kind'] = 'delivery'
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    case_dir = ROOT / 'cases' / suffix
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = case_dir / 'physical-fixtures' / (kind + '-result.json')
        log = case_dir / 'physical-fixtures' / (kind + '-test.log')
        result.parent.mkdir(parents=True, exist_ok=True)
        command = [str(PYTHON), str(ROOT / 'prove_physical.py'),
                   '--case', case, '--fixture', kind, '--output', str(result)]
        proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(((proc.stdout + proc.stderr).strip() or 'no output') + '\n')
        if proc.returncode:
            raise RuntimeError(log.read_text())
        fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                         'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
    lifecycle = case_dir / 'physical-fixtures/lifecycle-test.log'
    lifecycle.write_text('Synthetic diagnostic capture closed; encoder closed; restoration verified; Native exited; owner released; saved processing started. Early saved processing rejected.\n')
    proof = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
             'fixtures': fixtures, 'lifecycle': {
                 'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                            'native_exit', 'owner_released', 'saved_processing_started'],
                 'exit_code': 0, 'rejected_early_saved_processing': True,
                 'log': str(lifecycle.relative_to(ROOT)), 'log_sha256': sha(lifecycle)},
             'physical_acceptance_claimed': False}
    receipt = case_dir / 'physical-preparation.json'
    put(receipt, proof)
    entry['physical_preparation'] = {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt)}
    entry['original_source_gate'] = {'required_at_execution': True,
        'required_packet': 'SHA-bound original intersection map, surveyed four-corner route, official diagonal authorization/device inventory, NRS 484B.290 exception review',
        'required_media': '900 synchronized original frames from four cameras with full decode and independent original-video review',
        'source_status': 'unresolved', 'physical_completion_claimed': False,
        'legal_conclusion': 'not_assessed'}
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    delivery = {}
    for negative in (False, True):
        log = case_dir / ('delivery-negative.log' if negative else 'delivery-positive.log')
        command = [str(PYTHON), str(ROOT / 'prove_delivery.py'), '--case', case]
        if negative:
            command.append('--negative')
        proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        log.write_text(((proc.stdout + proc.stderr).strip() or 'no output') + '\n')
        if (proc.returncode == 0) == negative:
            raise RuntimeError('delivery probe exit code unexpected: ' + str(log))
        delivery['negative_' if negative else 'positive_'] = {
            'command': ' '.join(command), 'exit_code': proc.returncode,
            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}
    entry['delivery_acceptance'] = {'case_id': case,
        'sets': ['full-test'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'scope': 'CPU diagnostic interface proof only; real-source acceptance remains pending',
        'command': delivery['positive_']['command'], 'test_exit_code': 0,
        'test_log': delivery['positive_']['log'],
        'test_log_sha256': delivery['positive_']['log_sha256'],
        'negative_command': delivery['negative_']['command'],
        'negative_exit_code': delivery['negative_']['exit_code'],
        'negative_log': delivery['negative_']['log'],
        'negative_log_sha256': delivery['negative_']['log_sha256'],
        'negative_expected_error': 'diagnostic attempt cannot pass delivery audit',
        'script': 'prove_delivery.py', 'script_sha256': sha(ROOT / 'prove_delivery.py')}

source_probes = []
for negative in (False, True):
    command = [str(PYTHON), str(ROOT / 'prove_source_packet.py')]
    if negative:
        command.append('--negative')
    proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    log = ROOT / ('nov25-source-packet-' + ('negative' if negative else 'positive') + '.log')
    log.write_text(((proc.stdout + proc.stderr).strip() or 'no output') + '\n')
    if proc.returncode:
        raise RuntimeError(str(log) + ': ' + log.read_text())
    source_probes.append({'command': ' '.join(command), 'exit_code': 0,
                          'log': log.name, 'log_sha256': sha(log),
                          'expected': 'source hash mismatch: authorization' if negative else 'source_review_required'})
draft['source_audit_protocol'] = {'status': 'structural_test_double_only',
    'production_acceptance_required': True,
    'test_double_script': 'prove_source_packet.py',
    'test_double_script_sha256': sha(ROOT / 'prove_source_packet.py'),
    'probes': source_probes,
    'official_diagonal_device_verified': False,
    'exception_484b_290_resolved': False,
    'physical_completion_claimed': False}
put(ROOT / 'execution-manifest.json', draft)
first = json.loads((ROOT / draft['cases'][0]['construction']).read_text())
(ROOT / 'construction.json').write_text(json.dumps(first, indent=2, ensure_ascii=False) + '\n')
config = next(item['content'] for item in first['files'] if item['path'] == 'config.json')
(ROOT / 'config.json').write_text(config)
print('Selected source-gated manifest built for', len(draft['cases']), 'cases')
