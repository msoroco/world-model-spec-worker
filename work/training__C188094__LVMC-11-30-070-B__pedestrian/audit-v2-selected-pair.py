"""Bind the selected two-case manifest to public and saved CPU receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
pair_audit = runpy.run_path(str(HERE / 'audit-v2-pair.py'))['audit']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempts, saved):
    base = pair_audit(attempts, saved)
    manifest = read(HERE / 'v2-selected-pair-manifest.json')
    if len(manifest['cases']) != 2 or manifest['status'] != 'partial_selected_pair_cpu':
        raise ValueError('Selected pair manifest incomplete')
    hashes = []
    for number, entry in enumerate(manifest['cases'], 1):
        original = read(HERE / f'v2-probe{number}-manifest.json')['cases'][0]
        if entry != original:
            raise ValueError(f'Selected case {number} differs from tested exact entry')
        prefix = f'v2-selected-pair-probe{number}'
        compatibility = read(HERE / f'{prefix}-compatibility.json')
        processing = read(HERE / f'{prefix}-processing.json')
        negative = HERE / f'{prefix}-negative-analysis.log'
        construction = HERE / entry['construction']
        if compatibility['passed'] is not True or compatibility['case_id'] != entry['case_id'] or compatibility['construction_sha256'] != sha(construction):
            raise ValueError(f'Selected case {number} public compatibility differs')
        if compatibility['negative_log_sha256'] != sha(negative):
            raise ValueError(f'Selected case {number} negative source proof differs')
        if processing['passed'] is not True or processing['recorded_only'] is not True or processing['originals_preserved'] is not True or processing['timestamp_joins']['frames'] != 600:
            raise ValueError(f'Selected case {number} saved processing differs')
        if processing['analysis_revision']['construction_sha256'] != sha(construction):
            raise ValueError(f'Selected case {number} saved construction differs')
        hashes.append({'compatibility': sha(HERE / f'{prefix}-compatibility.json'),
                       'negative': sha(negative),
                       'processing': sha(HERE / f'{prefix}-processing.json')})
    return {'format': 'c188094-selected-pair-cpu-audit', 'passed': True,
            'manifest_sha256': sha(HERE / 'v2-selected-pair-manifest.json'),
            'case_ids': base['case_ids'], 'selected_receipt_hashes': hashes,
            'source_count_each': base['source_count_each'],
            'frames_each': base['frames_each'], 'fixed_configuration_checked': True,
            'diagnostic_only': True, 'native_physical_observed': False,
            'business_district_confirmed': False,
            'full_body_footprint_confirmed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for number in (1, 2):
        parser.add_argument(f'--attempt{number}', type=Path, required=True)
        parser.add_argument(f'--saved{number}', type=Path, required=True)
    args = parser.parse_args()
    result = audit({1: args.attempt1, 2: args.attempt2}, {1: args.saved1, 2: args.saved2})
    (HERE / 'v2-selected-pair-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
