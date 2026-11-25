"""Independent CPU audit of synthetic yield source, semantic mapping and receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def audit():
    plan = load(HERE / 'case-plan.json')
    frozen = ROOT / 'inputs' / HERE.name / 'assignment.json'
    if sha(frozen) != plan['sources'][0]['sha256']:
        raise ValueError('Frozen assignment binding differs')
    expected_terms = {row['term'] for row in plan['mandatory_observation_terms']}
    mapping = plan['source_observation_mapping']
    if len(expected_terms) != 14 or set(mapping) != expected_terms:
        raise ValueError('Frozen source observation mapping incomplete')
    allowed = {item['name'] for item in plan['observations']}
    if allowed != {'ego_body_pose', 'signal_phase_readback', 'frame_join'}:
        raise ValueError('Acquired channel roster differs')
    for term, row in mapping.items():
        if not row['source_refs'] or not row['evidence'] or not set(row['channels']) <= allowed:
            raise ValueError('Incomplete semantic mapping: ' + term)
        for ref in row['source_refs']:
            if not (ROOT / ref if ref.startswith('inputs/') else HERE / ref).is_file():
                raise ValueError('Semantic source absent: ' + ref)
    summaries = {}
    for label, clear, frame in (('wait-for-clearance', True, 340),
                                ('enter-during-occupancy', False, 260)):
        stem = f'current-v2-yield-{label}'
        manifest = HERE / f'{stem}-primary-manifest.json'
        public = HERE / f'{stem}-compatibility.json'
        saved = HERE / f'{stem}-saved-proof.json'
        receipt = load(public)
        saved_receipt = load(saved)
        native = HERE / f'{stem}-fixture/native_samples.jsonl'
        if not receipt['passed'] or not saved_receipt['passed']:
            raise ValueError('Public or saved proof failed: ' + label)
        if receipt['measurement_keys'] != ['cycle_requirement', 'yield_requirement']:
            raise ValueError('Source-bound measurement roster differs')
        observed = receipt['measurement_examples']['yield_requirement']['value']
        if observed != {'entry_frame': frame, 'yield_clear_at_entry': clear}:
            raise ValueError('Measured entry/occupation differs')
        if receipt['measurement_examples']['yield_requirement']['sources']['native_samples.jsonl'] != sha(native):
            raise ValueError('Original Native-shaped source hash differs')
        if saved_receipt['manifest_sha256'] != sha(manifest) or saved_receipt['compatibility_sha256'] != sha(public):
            raise ValueError('Saved proof binding differs')
        if not saved_receipt['source_hashes_preserved'] or saved_receipt['source_files'] != 613:
            raise ValueError('Recorded-only source inventory differs')
        if saved_receipt['original_native_observed'] or saved_receipt['selected_delivery']:
            raise ValueError('Synthetic diagnostic overclaims provenance')
        if 'Missing required source: road_geometry.json' not in (HERE / f'{stem}-negative.log').read_text():
            raise ValueError('Missing-source negative not retained')
        summaries[label] = {'manifest_sha256': sha(manifest),
                            'public_sha256': sha(public), 'saved_sha256': sha(saved),
                            'native_source_sha256': sha(native),
                            'entry_frame': frame, 'yield_clear_at_entry': clear}
    comparison = load(HERE / 'yield-comparison-proof.json')
    if not comparison['passed'] or comparison['entry_frames'] != [340, 260]:
        raise ValueError('Yield comparison proof differs')
    return {'format': 'c111071-yield-source-chain-audit-v1', 'passed': True,
            'frozen_assignment_sha256': sha(frozen), 'mapped_terms': len(mapping),
            'source_channels': sorted(allowed), 'cases': summaries,
            'comparison_sha256': sha(HERE / 'yield-comparison-proof.json'),
            'source_kind': 'synthetic_native_shaped_diagnostic',
            'original_native_observed': False, 'lawful_status_verified': False,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
