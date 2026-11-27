"""Seal an original freight attempt after three independent source reviews."""
import argparse
import json
from pathlib import Path

from freight_finalize import SOURCES, sha


def seal(attempt):
    attempt = Path(attempt).resolve()
    output = attempt / 'source-manifest.json'
    if output.exists():
        raise ValueError('Use a fresh original freight review attempt')
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    capture = attempt / 'capture-seal.json'
    if not capture.is_file():
        raise ValueError('Missing original Native capture seal')
    captured = json.loads(capture.read_text())
    if (captured.get('provenance_kind') != 'native' or
            captured.get('diagnostic_fixture') is not False or
            captured.get('frames') != 600):
        raise ValueError('Original Native freight capture seal differs')
    for name in SOURCES:
        prior = captured.get('sources', {}).get(name)
        if prior is not None and prior != sha(attempt / name):
            raise ValueError('Original freight capture source changed: ' + name)
    for name in ('commercial-status-review.json', 'sign-review.json',
                 'freight-purpose-review.json'):
        review = json.loads((attempt / name).read_text())
        if (review.get('source_kind') != 'original_native' or
                not review.get('source_basis') or
                review.get('legal_verdict') is not None):
            raise ValueError('Independent original freight review missing: ' + name)
    manifest = {'source_kind': 'original_native',
                'capture_seal_sha256': sha(capture),
                'sha256': {name: sha(attempt / name) for name in SOURCES},
                'legal_verdict': None}
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    print(seal(parser.parse_args().attempt))
