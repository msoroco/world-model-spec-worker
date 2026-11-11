"""Bind independent audit, physical outcome fixtures and lifecycle proof."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from both_hands_delivery_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FOLDER = ROOT / 'cases/both_hands_no_signal'
PHYSICAL = FOLDER / 'physical'
PHYSICAL.mkdir(exist_ok=True)
SOURCE = REPO / '.runtime-work/c111588-both-hands-primary-compat-a'
CASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__both_hands_no_signal'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


report = json.loads((SOURCE / 'analysis-report.json').read_text())
receipt = audit(SOURCE, report, receipt_dir=PHYSICAL / 'video-decodes')
audit_path = PHYSICAL / 'source-audit.json'
save(audit_path, receipt)
stale = json.loads(json.dumps(report))
stale['measurements']['both_hands_observation']['sources']['hand_contact_readback.jsonl'] = '0' * 64
try:
    audit(SOURCE, stale)
except ValueError as exc:
    if 'Stale or missing hand-control original' not in str(exc):
        raise
    negative = {'stale_hand_original_rejected': True, 'error': str(exc),
                'diagnostic_fixture_only': True}
else:
    raise AssertionError('stale lane original accepted')
negative_path = PHYSICAL / 'stale-hand-audit.json'
save(negative_path, negative)
fixtures = []
for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
    result = PHYSICAL / f'{kind}.json'
    log = PHYSICAL / f'{kind}.log'
    command = [sys.executable, str(ROOT / 'rider_physical_fixture.py'),
               '--source', str(SOURCE), '--kind', kind, '--output', str(result)]
    done = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    log.write_text(done.stdout + done.stderr)
    if done.returncode:
        raise RuntimeError('Physical fixture failed: ' + kind)
    fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                     'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                     'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
manifest_path = ROOT / 'both-hands-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = manifest['cases'][0]
life_log = ROOT / 'physical/lifecycle.log'
proof = {'format': 'worker-rider-physical-preparation', 'case_id': CASE,
         'construction_sha256': entry['construction_sha256'],
         'diagnostic_fixture_only': True, 'actual_native_capture': False,
         'physical_acceptance_claimed': False,
         'audit': {'receipt': str(audit_path.relative_to(ROOT)), 'sha256': sha(audit_path),
                   'stale_negative': str(negative_path.relative_to(ROOT)),
                   'stale_negative_sha256': sha(negative_path)},
         'fixtures': fixtures,
         'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                       'restoration_verified', 'native_exit', 'owner_released',
                       'saved_processing_started'], 'exit_code': 0,
                       'log': str(life_log.relative_to(ROOT)), 'log_sha256': sha(life_log)}}
proof_path = PHYSICAL / 'proof.json'
save(proof_path, proof)
entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(ROOT)),
                                 'sha256': sha(proof_path)}
save(manifest_path, manifest)
print('both-hands source/video audit and physical diagnostic fixtures passed')
