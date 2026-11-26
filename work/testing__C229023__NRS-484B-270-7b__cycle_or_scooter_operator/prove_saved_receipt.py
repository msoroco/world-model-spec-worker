"""Independently verify a recorded-only diagnostic replay receipt and sources."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(case_id, candidate, attempt, processing):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [item for item in manifest['cases'] if item['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('exact saved case missing')
    entry = entries[0]
    selected = (entry if candidate == 'primary' else
                next((item for item in entry['candidates'] if
                      item['id'] == candidate), None))
    if selected is None:
        raise ValueError('exact saved candidate missing')
    receipt = json.loads(Path(processing).read_text())
    if (receipt.get('case_id') != case_id or
            receipt.get('candidate_id') != candidate or
            receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('recorded-only replay receipt incomplete')
    if (receipt['analysis_revision']['construction_sha256'] !=
            selected['construction_sha256'] or
            receipt['timestamp_joins'].get('frames') != 900 or
            receipt['timestamp_joins'].get('passed') is not True or
            receipt['final_video_checks'].get('frames') != 900):
        raise ValueError('saved construction/frame/decoder binding differs')
    root = Path(attempt).resolve()
    for name, digest in receipt['original_source_hashes'].items():
        target = (root / name).resolve()
        if (not target.is_relative_to(root) or not target.is_file() or
                sha(target) != digest):
            raise ValueError('saved replay changed acquisition source: ' + name)
    return {'case_id': case_id, 'candidate_id': candidate,
            'processing_sha256': sha(processing),
            'original_source_count': len(receipt['original_source_hashes']),
            'recorded_only': True, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.candidate,
                           args.attempt, args.processing), sort_keys=True))
