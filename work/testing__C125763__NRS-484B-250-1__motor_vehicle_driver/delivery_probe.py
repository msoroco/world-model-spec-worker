"""Exercise saved-only four-view delivery with diagnostic source-shaped images."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import hashlib

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from test_saved_crossing import CrossingTest
from postprocess import run
from delivery_audit import audit
from native_run import PRODUCTION_DIMENSIONS


def production_camera_fixture(fixture):
    root = fixture.root
    site_path = root / 'site-context.json'
    site = json.loads(site_path.read_text())
    site['camera_dimensions'] = PRODUCTION_DIMENSIONS
    site_path.write_text(json.dumps(site) + '\n')
    frames = root / 'camera-frame-map.jsonl'
    rows = [json.loads(line) for line in frames.read_text().splitlines()]
    for index, row in enumerate(rows):
        for name, dimensions in PRODUCTION_DIMENSIONS.items():
            path = root / row['views'][name]['path']
            Image.new('RGB', tuple(dimensions), (index, 20, 40)).save(path)
            row['views'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    frames.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    manifest_path = root / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name in ('site-context.json', 'camera-frame-map.jsonl'):
        manifest[name]['sha256'] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    prefix = HERE.name + '__'
    if not args.case.startswith(prefix):
        raise ValueError('selected delivery case differs')
    case = args.case[len(prefix):]
    if case not in ('precedence', 'advance'):
        raise ValueError('unknown exact crossing case')
    fixture = CrossingTest('test_original_entry_clearance_and_exception_uncertainty')
    fixture.setUp()
    try:
        if case == 'advance':
            fixture.site['case_id'] = args.case
            fixture.ego = fixture.rows(11, 3, 8, 'x')
            fixture.write()
        fixture.seal_cameras()
        production_camera_fixture(fixture)
        output = fixture.root / 'saved-delivery'
        receipt = run(fixture.root, output, case)
        if receipt['physical_acceptance'] is not False or receipt['primary_full_decode'] is not True:
            raise ValueError('diagnostic delivery receipt overclaims')
        encoded = output / 'encoded-receipt.json'
        if args.negative:
            changed = json.loads(encoded.read_text())
            changed['videos']['overview']['sha256'] = '0' * 64
            encoded.write_text(json.dumps(changed) + '\n')
        checked = audit(fixture.root, output / 'saved-result.json', output / 'views', encoded,
                        probe_id=case, primary_path=output / 'primary.mkv',
                        composition_receipt=output / 'composition-receipt.json')
        print(json.dumps({'case_id': args.case,
                          'source_manifest_sha256': checked['source_manifest_sha256'],
                          'decoded_view_frames': checked['decoded_view_frames'],
                          'primary_full_decode': checked['composed_primary']['full_decode'],
                          'actual_pixels_verified': checked['actual_pixels_verified'],
                          'physical_acceptance': checked['physical_acceptance']}, sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
