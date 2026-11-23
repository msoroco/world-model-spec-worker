"""Reuse a decoded long synthetic composition after exact source-byte checks."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCES = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv', 'video_frames.jsonl')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def reuse(prior, prior_result, target):
    prior, prior_result, target = (Path(p).resolve() for p in
                                   (prior, prior_result, target))
    if any(REPO / '.runtime-work' not in p.parents for p in
           (prior, prior_result, target)):
        raise ValueError('Long diagnostic media must remain ignored')
    receipt_path = prior_result / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    frames = json.loads((target / 'config.json').read_text())['capture_frames']
    if not (frames in (36120, 36121, 36122)
            and receipt.get('passed') is True
            and receipt.get('recorded_only') is True
            and receipt.get('originals_preserved') is True
            and receipt.get('missing_evidence') is False
            and receipt.get('timestamp_joins', {}).get('frames') == frames
            and receipt.get('final_video_checks', {}).get('frames') == frames
            and receipt.get('physical_acceptance_claimed') is False
            and receipt.get('legal_acceptance_claimed') is False):
        raise ValueError('Prior synthetic saved composition lacks full proof')
    bindings = {}
    for name in SOURCES:
        left, right = prior / name, target / name
        digest = sha(left)
        if sha(right) != digest or receipt['original_source_hashes'].get(name) != digest:
            raise ValueError('Prior/current source differs: ' + name)
        bindings[name] = digest
    source = prior / 'raw.mkv'
    raw_sha = sha(source)
    if receipt['original_source_hashes'].get('raw.mkv') != raw_sha:
        raise ValueError('Prior composition differs from passed saved receipt')
    destination = target / 'raw.mkv'
    if destination.exists():
        raise ValueError('Fresh target must not have a composition')
    shutil.copyfile(source, destination)
    if sha(destination) != raw_sha:
        destination.unlink()
        raise ValueError('Copied composition differs')
    return {'format': 'c150142-current-long-composition-reuse-v1',
            'frames': frames, 'exact_source_hashes': bindings,
            'raw_sha256': raw_sha, 'composed_sha256': raw_sha,
            'prior_saved_receipt_sha256': sha(receipt_path),
            'reused_identical_synthetic_sources': True,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prior')
    parser.add_argument('prior_result')
    parser.add_argument('target')
    args = parser.parse_args()
    print(json.dumps(reuse(args.prior, args.prior_result, args.target),
                     indent=2, sort_keys=True))
