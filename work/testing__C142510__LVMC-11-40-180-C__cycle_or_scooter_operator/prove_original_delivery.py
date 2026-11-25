"""Mock-only CPU probe of original delivery audit wiring and missing-source rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, HERE, FIXED_SITE, audit_attempt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(case_id, negative):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if case_id not in {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('exact selected sidewalk case required')
    scratch = HERE.parents[1] / '.runtime-work' / 'c142510' / 'tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    if negative:
        audit_attempt(scratch / 'absent-original-attempt', case_id)
        raise ValueError('missing original attempt was accepted')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='mock-only-sidewalk-audit-') as dirname:
        root = Path(dirname)
        (root / 'source-manifest.json').write_text('{"mock_only":true}\n')
        site = {key: 'MOCK ONLY ' + key for key in FIXED_SITE}
        site.update({'case_id': case_id, 'reviewer': 'MOCK ONLY',
                     'physical_surface_kind': 'sidewalk', 'sidewalk_connected': True,
                     'rider_kind': 'bicycle'})
        (root / 'site-context.json').write_text(json.dumps(site) + '\n')
        cameras = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            path = root / (name + '.mkv')
            path.write_text('MOCK ONLY ' + name + '\n')
            cameras[name] = {'path': path.name, 'sha256': sha(path), 'frame_count': 900}
        (root / 'capture-identity.json').write_text(json.dumps({
            'case_id': case_id, 'source_kind': 'original_native_capture',
            'diagnostic_fixture': False,
            'source_manifest_sha256': sha(root / 'source-manifest.json'),
            'cameras': cameras}) + '\n')
        measurement = {'case_id': case_id, 'legal_verdict_claimed': False,
                       'source_sha256': {'road.xodr': 'MOCK ONLY'}}
        with patch('delivery_audit.measure', return_value=measurement) as measure, \
             patch('delivery_audit.decode_camera', return_value={'frames': 900}) as decode:
            report = audit_attempt(root, case_id)
            measure.assert_called_once()
            if decode.call_count != 4 or report['physical_acceptance'] is not False or report['legal_status'] != 'unresolved':
                raise ValueError('mock-only original audit wiring changed')
    return 'mock-only original delivery audit wiring passed: ' + case_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-missing-attempt', action='store_true')
    args = parser.parse_args()
    try:
        print(prove(args.case, args.negative_missing_attempt))
    except ValueError as error:
        print(str(error))
        raise SystemExit(2)
