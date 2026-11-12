"""Independent source-hash audit of all twenty C125697 construction proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(root=HERE, manifest=None, result=None):
    root = Path(root)
    manifest = manifest or json.loads((root / 'execution-manifest.json').read_text())
    result = result or json.loads((root / 'result.json').read_text())
    require(len(manifest.get('cases', [])) == 5, 'Five selected cases required')
    require(result.get('status') == 'partial' and
            result.get('assignment_id') == manifest.get('assignment_id'),
            'Truthful matching partial result required')
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        candidates = entry.get('candidates')
        require(isinstance(candidates, list) and len(candidates) == 3 and
                {c['id'] for c in candidates} == {'fallback1', 'fallback2', 'fallback3'},
                'Three exact fallbacks required: ' + case)
        knobs = [tuple(candidate.get('changed_knobs', [])) for candidate in candidates]
        require(all(knobs) and len(set(knobs)) == 3 and
                all(candidate.get('trigger', {}).get('metric') and
                    candidate['trigger'].get('failure_condition') for candidate in candidates),
                'Distinct physical-risk fallback triggers required: ' + case)
        for ident, selected in [('primary', entry)] + [(c['id'], c) for c in candidates]:
            construction = root / selected['construction']
            digest = selected['construction_sha256']
            require(construction.is_file() and sha(construction) == digest,
                    'Missing or changed exact construction: ' + case + '/' + ident)
            offline = selected.get('offline') or {}
            offline_log = root / offline.get('log', '__missing__')
            require(offline.get('exit_code') == 0 and
                    offline.get('construction_sha256') == digest and
                    offline_log.is_file() and sha(offline_log) == offline.get('log_sha256') and
                    '"offline_passed": true' in offline_log.read_text(),
                    'Missing exact offline proof: ' + case + '/' + ident)
            compatibility = selected.get('compatibility') or {}
            receipt_file = root / compatibility.get('receipt', '__missing__')
            log_file = root / compatibility.get('log', '__missing__')
            negative_file = root / compatibility.get('negative_log', entry.get('negative', {}).get('log', '__missing__'))
            require(receipt_file.is_file() and
                    sha(receipt_file) == compatibility.get('sha256') and
                    log_file.is_file() and negative_file.is_file(),
                    'Missing positive/negative compatibility proof: ' + case + '/' + ident)
            receipt = json.loads(receipt_file.read_text())
            require(receipt.get('passed') is True and receipt.get('case_id') == case and
                    receipt.get('candidate_id') == ident and
                    receipt.get('construction_sha256') == digest and
                    receipt.get('log_sha256') == sha(log_file) and
                    receipt.get('negative_log_sha256') == sha(negative_file) and
                    receipt.get('negative_removed') == 'crossing_history.jsonl' and
                    receipt.get('measurement_keys') and
                    receipt.get('checks') and
                    {'actual_analysis', 'negative_case_source', 'four_camera_sources',
                     'native_validation', 'lean_decoder', 'final_decode'} <= set(receipt['checks']),
                    'Invalid source-bound compatibility proof: ' + case + '/' + ident)
            saved_logs = []
            for proof in result.get('tests', []):
                command = proof.get('command', '')
                name = proof.get('log', '')
                if (proof.get('exit_code') != 0 or 'runtime.py process-saved' not in command or
                        'execution-manifest.json' not in command or
                        '--case ' + case + ' ' not in command or not name):
                    continue
                path = root / name
                if not path.is_file() or sha(path) != proof.get('sha256'):
                    continue
                try:
                    saved = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                if (saved.get('case_id') == case and saved.get('candidate_id') == ident and
                        saved.get('passed') is True and saved.get('recorded_only') is True and
                        saved.get('originals_preserved') is True and
                        saved.get('physical_acceptance_claimed') is False and
                        saved.get('legal_acceptance_claimed') is False and
                        saved.get('native_revision', {}).get('construction_sha256') == digest):
                    saved_logs.append(name)
            require(saved_logs, 'Missing recorded-only saved proof: ' + case + '/' + ident)
            rows.append({'case_id': case, 'candidate_id': ident,
                         'construction_sha256': digest, 'saved_log': saved_logs[-1]})
    return {'format': 'worker-c125697-delivery-audit', 'passed': True,
            'exact_constructions': len(rows), 'proofs': rows,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
