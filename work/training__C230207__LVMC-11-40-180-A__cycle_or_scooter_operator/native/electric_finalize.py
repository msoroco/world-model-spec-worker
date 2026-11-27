"""Recorded-only electric-device source gate before the sidewalk finalizer.

The original recording remains unmodified. Review evidence and Native actor
identity are checked again on the saved attempt before measurements are written.
"""
import argparse
import hashlib
import json
from pathlib import Path

from finalize import finalize as finalize_sidewalk
from electric_asset import review_digest


def validate_electric_recording(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / 'config.json').read_text())
    context = json.loads((attempt / 'restriction-context.json').read_text())
    kind = config.get('machine_class')
    if kind not in {'electric_bicycle', 'electric_scooter'} or config.get('rider_class') != kind:
        raise ValueError('Exact electric class in saved config required')
    review = config.get('electric_asset_review')
    root_text = config.get('electric_asset_source_root')
    if not isinstance(review, dict) or review.get('machine_class') != kind:
        raise ValueError('Saved electric asset review missing or changed')
    if not isinstance(root_text, str) or not Path(root_text).is_absolute():
        raise ValueError('Saved electric asset source root missing')
    root = Path(root_text).resolve()
    bound = context.get('electric_asset_binding')
    if not isinstance(bound, dict) or bound.get('machine_class') != kind or not bound.get('classification_review_bound'):
        raise ValueError('Original electric asset binding missing')
    if (bound.get('blueprint_id') != review.get('blueprint_id') or
            context.get('blueprint_id') != bound.get('blueprint_id')):
        raise ValueError('Saved electric blueprint and original binding differ')
    if bound.get('review_sha256') != review_digest(review):
        raise ValueError('Saved electric class review changed after Native acquisition')
    refs = review.get('source_refs')
    if not isinstance(refs, list) or not refs:
        raise ValueError('Original electric class source references missing')
    hashes = {}
    for ref in refs:
        relative = ref.get('path') if isinstance(ref, dict) else None
        if not isinstance(relative, str) or not relative:
            raise ValueError('Original electric asset source path missing')
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError('Original electric asset source unavailable')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != ref.get('sha256') or relative in hashes:
            raise ValueError('Original electric asset source changed')
        hashes[relative] = actual
    if hashes != bound.get('review_source_sha256'):
        raise ValueError('Original electric asset review source binding differs')
    poses_path = attempt / 'bicycle-poses.jsonl'
    if not poses_path.is_file():
        raise ValueError('Original electric actor poses missing')
    count = 0
    for line in poses_path.read_text().splitlines():
        row = json.loads(line)
        if (row.get('machine_class') != kind or
                row.get('electric_asset_blueprint_id') != bound['blueprint_id'] or
                row.get('rider_blueprint_id') != bound['blueprint_id'] or
                row.get('rider_actor_id') != bound.get('native_actor_id')):
            raise ValueError('Original electric pose and reviewed asset binding differ')
        count += 1
    if count != 600:
        raise ValueError('Original electric 600-frame pose source missing')
    return {'machine_class': kind, 'blueprint_id': bound['blueprint_id'],
            'native_actor_id': bound['native_actor_id'],
            'review_sha256': bound['review_sha256'],
            'review_source_sha256': hashes,
            'original_class_pixels_verified': False,
            'physical_acceptance_claimed': False}


def finalize(attempt, output):
    binding = validate_electric_recording(attempt)
    report = finalize_sidewalk(attempt, output)
    report['electric_asset_binding'] = binding
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
