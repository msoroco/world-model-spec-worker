"""Hash an original taxi attempt only after independent review files exist."""
import argparse
import json
from pathlib import Path

from finalize_original import SOURCES, sha


def seal(attempt):
    attempt = Path(attempt).resolve()
    output = attempt / 'source-manifest.json'
    if output.exists():
        raise ValueError('Retain the existing source manifest; use a fresh attempt')
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing original or review source: ' + name)
    for name in ('taxicab-review.json', 'commercial-status-review.json', 'sign-review.json',
                 'passenger-purpose-review.json', 'ordinary-rules-review.json'):
        review = json.loads((attempt / name).read_text())
        if review.get('source_kind') != 'original_native' or not review.get('source_basis'):
            raise ValueError('Independent original review is missing: ' + name)
    seal_path = attempt / 'capture-seal.json'
    if not seal_path.is_file():
        raise ValueError('Original capture seal is missing')
    capture_seal = json.loads(seal_path.read_text())
    if (capture_seal.get('provenance_kind') != 'native' or
            capture_seal.get('diagnostic_fixture') is not False or
            capture_seal.get('frames') != 600):
        raise ValueError('Original Native capture seal differs')
    for name in SOURCES:
        prior = capture_seal.get('sources', {}).get(name)
        if prior is not None and prior != sha(attempt / name):
            raise ValueError('Original captured source changed: ' + name)
    manifest = {'source_kind': 'original_native',
                'sha256': {name: sha(attempt / name) for name in SOURCES},
                'capture_seal_sha256': sha(seal_path),
                'legal_verdict': None}
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(seal(args.attempt))
