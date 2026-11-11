"""Bind independent device audits, three physical outcome fixtures and saved proof."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from rider_device_delivery_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


for device in ('electric_bicycle', 'electric_scooter'):
    slug = device + '_signal_once'
    case = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__' + slug
    folder = ROOT / 'cases' / slug
    physical = folder / 'physical'
    physical.mkdir(exist_ok=True)
    source = REPO / '.runtime-work' / ('c111588-' + device + '-primary-compat-final-b')
    report = json.loads((source / 'analysis-report.json').read_text())
    receipt = audit(source, report, device, receipt_dir=physical / 'video-decodes')
    audit_path = physical / 'source-audit.json'
    save(audit_path, receipt)
    stale = json.loads(json.dumps(report))
    stale['measurements']['electric_device_observation']['sources']['device_blueprint_readback.json'] = '0' * 64
    try:
        audit(source, stale, device)
    except ValueError as exc:
        if 'Stale or missing electric device original' not in str(exc):
            raise
        negative = {'stale_device_blueprint_original_rejected': True, 'error': str(exc), 'diagnostic_fixture_only': True}
    else:
        raise AssertionError('Stale device blueprint original accepted')
    negative_path = physical / 'stale-device-audit.json'
    save(negative_path, negative)
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = physical / (kind + '.json')
        log = physical / (kind + '.log')
        command = [sys.executable, str(ROOT / 'rider_physical_fixture.py'), '--source', str(source), '--kind', kind, '--output', str(result)]
        done = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
        log.write_text(done.stdout + done.stderr)
        if done.returncode:
            raise RuntimeError(kind + ' physical fixture failed: ' + log.read_text())
        fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                         'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
    manifest_path = ROOT / (device.replace('_', '-') + '-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    life_log = ROOT / 'physical/lifecycle.log'
    proof = {'format': 'worker-rider-physical-preparation', 'case_id': case,
             'construction_sha256': entry['construction_sha256'],
             'diagnostic_fixture_only': True, 'actual_native_capture': False,
             'physical_acceptance_claimed': False,
             'audit': {'receipt': str(audit_path.relative_to(ROOT)), 'sha256': sha(audit_path),
                       'stale_negative': str(negative_path.relative_to(ROOT)),
                       'stale_negative_sha256': sha(negative_path)},
             'fixtures': fixtures,
             'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started'],
                           'exit_code': 0, 'log': str(life_log.relative_to(ROOT)), 'log_sha256': sha(life_log)}}
    proof_path = physical / 'proof.json'
    save(proof_path, proof)
    entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(ROOT)), 'sha256': sha(proof_path)}
    save(manifest_path, manifest)
    saved = REPO / '.runtime-work' / ('c111588-' + ('ebike' if device=='electric_bicycle' else 'escooter') + '-saved-proof') / 'v0001'
    assert json.loads((saved / 'processing.json').read_text())['passed']
    shutil.copy2(saved / 'processing.json', folder / 'saved-receipt.json')
    shutil.copy2(saved / 'analysis.log', folder / 'saved-analysis.log')
    proof = {'format': 'worker-rider-electric-device-primary-proof', 'case_id': case,
             'construction_sha256': entry['construction_sha256'],
             'measurement_contract_sha256': sha(folder / 'measurement-contract.json'),
             'fixture_recipe_sha256': sha(folder / 'diagnostic-recipe.json'),
             'offline_passed': True, 'compatibility_passed': True,
             'missing_device_blueprint_rejected': True, 'saved_processing_passed': True,
             'saved_receipt': {'file': 'saved-receipt.json', 'sha256': sha(folder / 'saved-receipt.json')},
             'independent_audit': entry['physical_preparation'],
             'fallbacks': [c['id'] for c in entry['candidates']],
             'device_class_confirmed': None, 'electric_drive_verified': None,
             'diagnostic_fixture_only': True, 'physical_acceptance_claimed': False,
             'legal_acceptance_claimed': False}
    save(folder / 'proof.json', proof)
    print(device, 'independent audit, physical fixtures and saved proof bound', flush=True)
