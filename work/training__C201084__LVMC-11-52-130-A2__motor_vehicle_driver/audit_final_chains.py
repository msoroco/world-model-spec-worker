"""Independently bind all final delivery-manifest diagnostic CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest_path = HERE / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    manifest = read(manifest_path)
    cases = {case['case_id'].rsplit('__', 1)[-1]: case for case in manifest['cases']}
    require(set(cases) == set(GROUPS) and manifest['assignment_id'] == HERE.name,
            'Selected case coverage differs')
    bindings = {}
    for group in GROUPS:
        case = cases[group]
        candidate_map = {'primary': case,
                         **{candidate['id']: candidate for candidate in case['candidates']}}
        require(set(candidate_map) == {'primary', 'fallback1', 'fallback2', 'fallback3'},
                'Selected candidate coverage differs: ' + group)
        for candidate, plan in candidate_map.items():
            prefix = 'final-' + group + '-' + candidate
            special = False
            offline_log = HERE / (prefix + ('-offline-v2.log' if special else '-offline.log'))
            selection_path = HERE / (prefix + '-offline-selection.json')
            compat_path = HERE / (prefix + '-compatibility.log')
            positive_path = HERE / (prefix + ('-analysis.log' if not special else '-analysis.log'))
            negative_path = HERE / (prefix + '-negative-analysis.log')
            saved_path = HERE / (prefix + '-saved.log')
            proof_path = HERE / (prefix + '-proof.json')
            files = [offline_log, selection_path, compat_path, positive_path,
                     negative_path, saved_path, proof_path]
            require(all(path.is_file() and path.stat().st_size <= 2*1024*1024 for path in files),
                    'Selected proof missing or oversized: ' + prefix)
            offline = read(offline_log)
            selection = read(selection_path)
            compat = read(compat_path)
            saved = read(saved_path)
            proof = read(proof_path)
            expected = {'case_id': case['case_id'], 'candidate_id': candidate,
                        'construction_sha256': plan['construction_sha256']}
            require(all(selection.get(key) == value for key, value in expected.items()) and
                    selection.get('manifest_sha256') == manifest_sha,
                    'Offline selection mismatch: ' + prefix)
            require(offline.get('case_id') == case['case_id'] and
                    offline.get('candidate_id') == candidate and
                    offline.get('offline_passed') is True and
                    offline.get('simulation_started') is False,
                    'Offline receipt mismatch: ' + prefix)
            require(compat.get('passed') is True and
                    all(compat.get(key) == value for key, value in expected.items()) and
                    compat.get('negative_log_sha256') == sha(negative_path) and
                    compat.get('negative_error_contains') in negative_path.read_text() and
                    compat.get('scope') == 'diagnostic software compatibility only',
                    'Positive or negative compatibility mismatch: ' + prefix)
            require(saved.get('passed') is True and saved.get('recorded_only') is True and
                    saved.get('case_id') == case['case_id'] and
                    saved.get('candidate_id') == candidate and
                    saved.get('native_revision', {}).get('construction_sha256') ==
                    plan['construction_sha256'] and
                    saved.get('originals_preserved') is True and
                    saved.get('physical_acceptance_claimed') is False and
                    saved.get('legal_acceptance_claimed') is False,
                    'Saved receipt mismatch: ' + prefix)
            if special:
                require(proof.get('manifest_sha256_at_run') == manifest_sha and
                        proof.get('construction_sha256') == plan['construction_sha256'] and
                        proof.get('accepted') is False and
                        proof.get('offline_log_sha256') == sha(offline_log) and
                        proof.get('compatibility_receipt_sha256') == sha(compat_path) and
                        proof.get('negative_log_sha256') == sha(negative_path) and
                        proof.get('saved_receipt_sha256') == sha(saved_path),
                        'Reference primary proof mismatch')
            else:
                require(proof.get('selected_manifest_sha256') == manifest_sha and
                        proof.get('cpu_chain_passed') is True and
                        proof.get('delivery_ready') is False and
                        all(proof.get('receipts', {}).get(path.name) == sha(path)
                            for path in files[:-1]),
                        'Selected chain proof mismatch: ' + prefix)
            bindings[group + '/' + candidate] = sha(proof_path)
    return {'format': 'c201084-final-candidate-cpu-audit-v1',
            'passed': True, 'diagnostic_only': True,
            'final_manifest_sha256': manifest_sha,
            'candidate_proof_sha256': bindings,
            'selected_cases': 8, 'candidate_chains_proven': 32,
            'original_native_observed': False, 'delivery_ready': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    (HERE / 'final-chains-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
