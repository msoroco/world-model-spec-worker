"""Independent source-level audit for the C295180 stopped/rolling pair."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_stop_line import measure
from stop_line_request import CASES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(full_stop_dir, rolling_dir):
    full_stop_dir, rolling_dir = Path(full_stop_dir), Path(rolling_dir)
    a = measure(full_stop_dir, CASES['full_stop'])
    b = measure(rolling_dir, CASES['rolling'])
    source_names = ('road.xodr',)
    refs = [json.loads((root / 'stop_reference.json').read_text())
            for root in (full_stop_dir, rolling_dir)]
    for ref in refs:
        ref.pop('case_id', None)
    if refs[0] != refs[1] or any(sha(full_stop_dir / name) != sha(rolling_dir / name)
                                   for name in source_names):
        raise ValueError('Fixed stop sign, line or intersection source differs')
    if a['source_kind'] != b['source_kind']:
        raise ValueError('Comparison source provenance differs')
    if a['source_seal_sha256'] == b['source_seal_sha256']:
        raise ValueError('Comparison reuses one saved source seal')
    if not a['complete_stop_before_line_diagnostic'] or b['complete_stop_before_line_diagnostic']:
        raise ValueError('Controlled stop diagnostic difference absent')
    return {'format': 'c295180-independent-stop-comparison-v1',
            'case_ids': [CASES['full_stop'], CASES['rolling']],
            'fixed_source_sha256': {name: sha(full_stop_dir / name)
                                    for name in source_names},
            'normalized_stop_reference': refs[0],
            'measurements': [a, b], 'comparison_passed': True,
            'physical_completion_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-stop-dir', required=True)
    parser.add_argument('--rolling-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.full_stop_dir, args.rolling_dir), sort_keys=True))
