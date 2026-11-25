"""Independent static audit of the exact C125751 CPU delivery preparations."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMES = {'source_verified_signal_exclusion', 'source_verified_off_subsection_4',
         'source_verified_opposite_intends_left'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit(root=ROOT, manifest=None):
    root = Path(root)
    manifest = manifest or json.loads((root / 'execution-manifest.json').read_text())
    entries = manifest.get('cases', [])
    require({e['case_id'].split('__')[-1] for e in entries} == NAMES and len(entries) == 3,
            'Exact three-case delivery inventory differs')
    checked = []
    for entry in entries:
        case_id = entry['case_id']
        candidates = entry.get('candidates', [])
        require(len(candidates) == 1 and candidates[0]['id'] == 'fallback1' and
                entry.get('candidate_risk', {}).get('status') == 'physical',
                'Exact physical fallback missing: ' + case_id)
        for candidate_id, selected in [('primary', entry), ('fallback1', candidates[0])]:
            label = case_id + '/' + candidate_id
            construction = root / selected['construction']
            digest = selected['construction_sha256']
            require(construction.is_file() and sha(construction) == digest,
                    'Changed exact construction: ' + label)
            bundle = json.loads(construction.read_text())
            require(bundle.get('case_id') == case_id and bundle.get('actor') == 'motor_vehicle_driver',
                    'Wrong construction identity: ' + label)
            offline = selected.get('offline', {})
            require(offline.get('exit_code') == 0 and offline.get('construction_sha256') == digest and
                    offline.get('command') and sha(root / offline.get('log', '__missing__')) == offline.get('log_sha256'),
                    'Missing exact offline CPU proof: ' + label)
            compatible = selected.get('compatibility', {})
            receipt_path = root / compatible.get('receipt', '__missing__')
            require(receipt_path.is_file() and sha(receipt_path) == compatible.get('sha256'),
                    'Changed compatibility receipt: ' + label)
            receipt = json.loads(receipt_path.read_text())
            require(receipt.get('passed') is True and receipt.get('case_id') == case_id and
                    receipt.get('candidate_id') == candidate_id and
                    receipt.get('construction_sha256') == digest and
                    receipt.get('negative_removed') == 'crossing_history.jsonl' and
                    {'native_validation', 'lean_decoder', 'final_decode', 'negative_case_source'}
                    <= set(receipt.get('checks', [])) and
                    sha(root / compatible['log']) == receipt.get('log_sha256') and
                    sha(root / compatible['negative_log']) == receipt.get('negative_log_sha256'),
                    'Incomplete positive/negative compatibility: ' + label)
            saved_spec = selected['saved_processing_diagnostic']
            saved_path = root / saved_spec['receipt']
            require(saved_spec.get('exit_code') == 0 and saved_spec.get('recorded_only') is True and
                    sha(saved_path) == saved_spec.get('sha256'),
                    'Changed recorded-only proof: ' + label)
            saved = json.loads(saved_path.read_text())
            require(saved.get('passed') is True and saved.get('recorded_only') is True and
                    saved.get('originals_preserved') is True and
                    saved.get('physical_acceptance_claimed') is False and
                    saved.get('native_revision', {}).get('construction_sha256') == digest,
                    'Recorded-only processing changed originals or asserted physical acceptance: ' + label)
            checked.append({'case_id': case_id, 'candidate': candidate_id,
                            'construction_sha256': digest, 'compatibility_sha256': sha(receipt_path),
                            'saved_sha256': sha(saved_path)})
        physical = entry['physical_preparation']
        receipt_path = root / physical['receipt']
        require(sha(receipt_path) == physical['sha256'], 'Physical outcome proof changed: ' + case_id)
        proof = json.loads(receipt_path.read_text())
        require({x['kind'] for x in proof['fixtures']} ==
                {'complete_motion', 'incomplete_motion', 'missing_evidence'} and
                proof['lifecycle']['events'] == ['capture_finished', 'encoders_closed',
                                               'restoration_verified', 'native_exit',
                                               'owner_released', 'saved_processing_started'],
                'Physical outcome or lifecycle inventory changed: ' + case_id)
        acceptance = entry['delivery_acceptance']
        require(acceptance['test_exit_code'] == 0 and acceptance['negative_exit_code'] != 0 and
                sha(root / acceptance['test_log']) == acceptance['test_log_sha256'] and
                sha(root / acceptance['negative_log']) == acceptance['negative_log_sha256'] and
                acceptance['negative_expected_error'] in (root / acceptance['negative_log']).read_text(),
                'Independent delivery acceptance boundary failed: ' + case_id)
    return {'format': 'worker-c125751-delivery-audit', 'passed': True,
            'exact_constructions': len(checked), 'proofs': checked,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
