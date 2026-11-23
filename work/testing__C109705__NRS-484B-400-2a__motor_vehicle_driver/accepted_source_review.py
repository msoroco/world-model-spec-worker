"""Inventory and hash-check frozen accepted sources before any reuse decision.

Metadata membership is not physical or statutory coverage. Missing original
assets remain unknown; this module never substitutes metadata for measurements.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(evidence_path, repo_root, source_root=None):
    evidence_path, repo_root = Path(evidence_path), Path(repo_root)
    evidence = json.loads(evidence_path.read_text())
    records = []
    seen = set()
    for item in evidence['recordings']:
        rid = item['recording_id']
        if rid in seen or item['membership']['recording_id'] != rid:
            raise ValueError('duplicate or mismatched recording identity')
        seen.add(rid)
        sources = item.get('sources', [])
        if len(sources) != 1:
            raise ValueError('accepted metadata inventory missing')
        metadata_path = repo_root / sources[0]['path']
        if digest(metadata_path) != sources[0]['sha256']:
            raise ValueError('frozen accepted metadata hash mismatch')
        metadata = json.loads(metadata_path.read_text())
        membership = item['membership']
        for key in ('recording_id', 'law_id', 'cell_id', 'actor', 'case_id'):
            if metadata.get(key) != membership[key]:
                raise ValueError('accepted metadata identity mismatch: ' + key)
        acceptance = metadata.get('acceptance', {})
        assets = {}
        for label, source_key, hash_key in (
                ('trace', 'trace_source', 'trace_sha256'),
                ('video', 'video_source', 'video_sha256'),
                ('delivery_audit', 'delivery_audit', 'delivery_audit_sha256')):
            source = acceptance.get(source_key)
            expected = acceptance.get(hash_key)
            if not source or not expected:
                raise ValueError('accepted original source inventory missing: ' + label)
            path = Path(source)
            if source_root is not None:
                path = Path(source_root) / rid / ('trace.json' if label == 'trace' else
                                                 'evidence/raw.mkv' if label == 'video' else
                                                 'evidence/delivery-audit-final.json')
            available = path.is_file()
            if available and digest(path) != expected:
                raise ValueError('accepted original asset hash mismatch: ' + label)
            assets[label] = {'path': str(path), 'sha256': expected,
                             'hash_verified': available}
        records.append({'recording_id': rid, 'case_id': membership['case_id'],
                        'metadata_sha256': sources[0]['sha256'],
                        'original_assets': assets,
                        'source_review_status': 'original_assets_hash_verified' if all(
                            asset['hash_verified'] for asset in assets.values()) else
                            'original_assets_unavailable'})
    return {'format': 'worker-400-2a-accepted-source-inventory',
            'law_id': 'NRS-484B-400-2a', 'records': records,
            'physical_coverage_verdict': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = review(args.evidence, args.repo_root)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
