"""Independently check the selected stand candidates and pinned offline receipts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    folder = ROOT/'selected-all'
    manifest_path = folder/'draft-manifest.json'
    proof_path = folder/'draft-proof.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c135709-selected-offline-proof-v1' or
        proof['manifest_sha256'] != sha(manifest_path) or
        proof['all_passed'] is not True or len(proof['results']) != 8 or
        proof['original_native_observed'] is not False):
        raise ValueError('Selected offline proof coverage differs')
    expected = {(ROOT.name+'__'+witness, candidate)
        for witness in ('reference', 'contrast')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    seen = set()
    for entry in manifest['cases']:
        validate(folder, entry, 'NRS-484B-517', 'C135709',
                 required=False, require_alternate=True, candidate_count=4)
    for row in proof['results']:
        key = row['case_id'], row['candidate_id']
        if key not in expected or key in seen or row['exit_code'] != 0:
            raise ValueError('Selected candidate missing or duplicated')
        seen.add(key)
        witness = key[0].split('__')[-1]
        construction = folder/witness/key[1]/'construction.json'
        log = ROOT/row['log']
        runtime_output = REPO/row['runtime_output']
        if (sha(construction) != row['construction_sha256'] or
            sha(log) != row['log_sha256'] or
            'offline_passed' not in log.read_text() or
            not (runtime_output/'offline.log').is_file() or
            'Ran 2 tests' not in (runtime_output/'offline.log').read_text() or
            'OK' not in (runtime_output/'offline.log').read_text()):
            raise ValueError('Selected offline command or test evidence differs')
        cfg = json.loads(next(item['content'] for item in
            json.loads(construction.read_text())['files'] if item['path']=='config.json'))
        if (cfg['assignment_sha256'] != sha(REPO/'inputs'/ROOT.name/'assignment.json') or
            cfg['case_plan_sha256'] != sha(ROOT/'case-plan.json') or
            cfg['selected_case_id'] != row['case_id'] or
            cfg['requested_stand_occupancy'] != (witness == 'contrast')):
            raise ValueError('Selected candidate changed source or comparison variable')
        if key[1] == 'fallback3' and cfg['motion_policy'] != 'pre_entry_dwell':
            raise ValueError('Third fallback no longer preserves stand comparison')
    if seen != expected:
        raise ValueError('Selected offline coverage incomplete')
    receipt = {'format': 'c135709-independent-selected-offline-audit-v1',
        'manifest_sha256': sha(manifest_path), 'proof_sha256': sha(proof_path),
        'candidates_checked': len(seen), 'original_native_observed': False,
        'delivery_ready': False}
    path = folder/'draft-audit.json'
    path.write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
