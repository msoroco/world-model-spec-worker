"""Saved-only 250(1) finalization, four-view encoding and audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit
from encode_views import compose_primary, encode
from native_history_capture import _retained_file
from native_run import CASES
from saved_finalizer import finalize


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run(attempt, output, probe_id):
    """Process a retained attempt without changing its original Native sources."""
    if probe_id not in CASES:
        raise ValueError('unknown exact timing case')
    attempt, output = Path(attempt), Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('fresh empty postprocessing output required')
    manifest = _retained_file(attempt, 'source-manifest.json')
    source_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    site = json.loads(_retained_file(attempt, 'site-context.json').read_text(
        encoding='utf-8'))
    dimensions = site.get('camera_dimensions')
    output.mkdir(parents=True, exist_ok=True)
    saved_path = output / 'saved-result.json'
    saved = finalize(attempt, saved_path, expected_manifest_sha256=source_hash,
                     case_id=site['assignment_id'] + '__' + probe_id)
    videos = output / 'views'
    encoded = encode(attempt, videos, camera_dimensions=dimensions)
    encoded_path = output / 'encoded-receipt.json'
    _write(encoded_path, encoded)
    primary_path = output / 'primary.mkv'
    composed = compose_primary(attempt, videos, primary_path, encoded_path)
    composition_path = output / 'composition-receipt.json'
    _write(composition_path, composed)
    independent = audit(attempt, saved_path, videos, encoded_path,
                        probe_id=probe_id, primary_path=primary_path,
                        composition_receipt=composition_path)
    independent_path = output / 'independent-delivery-audit.json'
    _write(independent_path, independent)
    return {'probe_id': probe_id, 'saved_result': saved_path.name,
            'encoded_receipt': encoded_path.name,
            'composition_receipt': composition_path.name,
            'independent_delivery_audit': independent_path.name,
            'source_manifest_sha256': source_hash,
            'original_frames': saved['original_frame_count'],
            'primary_full_decode': independent['composed_primary']['full_decode'],
            'diagnostic_fixture': saved['diagnostic_fixture'],
            'physical_acceptance': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--probe', choices=CASES, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output, args.probe), sort_keys=True))


if __name__ == '__main__':
    main()
