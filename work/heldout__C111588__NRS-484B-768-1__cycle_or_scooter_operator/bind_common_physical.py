"""Bind current exact source audits and synthetic physical-preparation fixtures."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
MANIFESTS = {
    'bicycle_signal_once': 'first-execution-manifest.json',
    'bicycle_no_signal': 'no-signal-manifest.json',
    'bicycle_signal_continuous': 'continuous-manifest.json',
    'electric_bicycle_signal_once': 'electric-bicycle-manifest.json',
    'electric_scooter_signal_once': 'electric-scooter-manifest.json',
    'turn_lane_no_signal': 'turn-lane-manifest.json',
    'both_hands_no_signal': 'both-hands-manifest.json',
    'safety_wide': 'safety-wide-manifest.json',
    'safety_narrow': 'safety-narrow-manifest.json',
}

def sha(path):
    return sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

for slug, manifest_name in MANIFESTS.items():
    case = PREFIX + slug
    folder = ROOT / 'cases' / slug / 'physical-j'
    folder.mkdir(exist_ok=True)
    source = REPO / '.runtime-work' / f'c111588-common-{slug}-primary-compat-j'
    env = {**os.environ, 'PYTHONPATH': 'runtime/scenario_pipeline'}
    cmd = [sys.executable, str(ROOT / 'rider_acceptance_check.py'), '--case', case,
           '--attempt', str(source.relative_to(REPO))]
    positive = subprocess.run(cmd, cwd=REPO, env=env, text=True, capture_output=True)
    positive_log = folder / 'source-audit.log'
    positive_log.write_text(positive.stdout + positive.stderr)
    if positive.returncode:
        raise RuntimeError(slug + ' source audit: ' + positive_log.read_text())
    source_audit = folder / 'source-audit.json'
    save(source_audit, json.loads(positive.stdout))
    negative = subprocess.run(cmd + ['--negative'], cwd=REPO, env=env, text=True, capture_output=True)
    negative_log = folder / 'stale-source.log'
    negative_log.write_text(negative.stdout + negative.stderr)
    if negative.returncode == 0 or 'Stale or missing original source: rider_arm_bones.jsonl' not in negative_log.read_text():
        raise RuntimeError(slug + ' stale original audit failed: ' + negative_log.read_text())
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result_path = folder / (kind + '.json')
        log = folder / (kind + '.log')
        command = [sys.executable, str(ROOT / 'rider_physical_fixture.py'), '--source', str(source),
                   '--kind', kind, '--output', str(result_path)]
        result = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(slug + ' ' + kind + ': ' + log.read_text())
        fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                         'result': str(result_path.relative_to(ROOT)), 'result_sha256': sha(result_path)})
    manifest_path = ROOT / manifest_name
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    life = ROOT / 'physical/lifecycle.log'
    proof = {'format': 'worker-rider-physical-preparation', 'case_id': case,
             'construction_sha256': entry['construction_sha256'],
             'diagnostic_fixture_only': True, 'actual_native_capture': False,
             'physical_acceptance_claimed': False,
             'audit': {'receipt': str(source_audit.relative_to(ROOT)), 'sha256': sha(source_audit),
                       'stale_negative': str(negative_log.relative_to(ROOT)),
                       'stale_negative_sha256': sha(negative_log)},
             'fixtures': fixtures,
             'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started'],
                           'exit_code': 0, 'log': str(life.relative_to(ROOT)), 'log_sha256': sha(life)}}
    proof_path = folder / 'proof.json'
    save(proof_path, proof)
    entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(ROOT)), 'sha256': sha(proof_path)}
    save(manifest_path, manifest)
    print(slug, 'source audit, stale negative and physical fixtures bound', flush=True)
