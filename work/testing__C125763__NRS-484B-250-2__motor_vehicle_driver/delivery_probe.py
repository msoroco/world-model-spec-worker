"""Source-bound CPU delivery audit probe for one exact timing case."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys

from PIL import Image


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from test_native_history_capture import CaptureTest  # noqa: E402
from native_history_capture import CAMERAS, capture  # noqa: E402
from native_run import PRODUCTION_DIMENSIONS  # noqa: E402
from postprocess import run as process_attempt  # noqa: E402
from delivery_audit import audit  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    prefix = HERE.name + '__'
    if not args.case.startswith(prefix):
        raise ValueError('selected delivery case differs')
    probe = args.case[len(prefix):]
    if probe not in ('entry_below', 'entry_inside', 'entry_above'):
        raise ValueError('unknown timing case')
    fixture = CaptureTest('test_original_clock_and_footprints_feed_measurement')
    fixture.setUp()
    try:
        fixture.scene['camera_dimensions'] = PRODUCTION_DIMENSIONS
        fixture.packet.write_text(json.dumps(fixture.scene) + '\n')
        pngs = {}
        for name in CAMERAS:
            stream = io.BytesIO()
            Image.new('RGB', tuple(PRODUCTION_DIMENSIONS[name]), 'black').save(
                stream, format='PNG')
            pngs[name] = stream.getvalue()
        readers = {name: lambda frame, png=pngs[name]: {'frame': frame,
                   'png_bytes': png} for name in CAMERAS}
        attempt = fixture.root / 'source-attempt'
        capture(fixture.world, fixture.packet, fixture.ego, fixture.other,
                attempt, 4, camera_readers=readers,
                camera_dimensions=PRODUCTION_DIMENSIONS)
        output = fixture.root / 'saved-delivery'
        receipt = process_attempt(attempt, output, probe)
        if receipt['physical_acceptance'] is not False or receipt['primary_full_decode'] is not True:
            raise ValueError('diagnostic delivery receipt overclaims')
        encoded = output / 'encoded-receipt.json'
        if args.negative:
            changed = json.loads(encoded.read_text())
            changed['videos']['overview']['sha256'] = '0' * 64
            encoded.write_text(json.dumps(changed) + '\n')
        inspected = audit(attempt, output / 'saved-result.json', output / 'views',
                          encoded, probe_id=probe, primary_path=output / 'primary.mkv',
                          composition_receipt=output / 'composition-receipt.json')
        print(json.dumps({'case_id': args.case,
            'source_manifest_sha256': inspected['source_manifest_sha256'],
            'decoded_view_frames': inspected['decoded_view_frames'],
            'primary_full_decode': inspected['composed_primary']['full_decode'],
            'actual_pixels_verified': inspected['actual_pixels_verified'],
            'physical_acceptance': inspected['physical_acceptance']}, sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
