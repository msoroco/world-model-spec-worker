"""Mock-only CPU probe of the independent original delivery audit wiring."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, HERE, audit_attempt
from reviewed_source import FIELDS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(case_id, negative):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if case_id not in {item['case_id'] for item in manifest['cases']}:
        raise ValueError('exact selected case required')
    name = case_id.removeprefix(ASSIGNMENT + '__')
    scratch = HERE.parents[1] / '.runtime-work' / 'c149470' / 'tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    if negative:
        audit_attempt(scratch / 'absent-original-site.json', scratch, name)
        raise ValueError('missing reviewed source was accepted')
    hashes = {field: hashlib.sha256(('MOCK ONLY ' + field).encode()).hexdigest()
              for field in FIELDS}
    reviewed = {'site_sha256': 'a' * 64, 'source_hashes': hashes}
    with tempfile.TemporaryDirectory(dir=scratch, prefix='mock-only-delivery-') as dirname:
        root = Path(dirname)
        rows = root / 'original-bus-frames.jsonl'
        rows.write_text(''.join(json.dumps({'original_frame': 100 + index,
                                           'time_s': index / 20,
                                           'mock_only': True}) + '\n'
                                for index in range(900)))
        cameras = {}
        archives = {}
        frame_map = [{'original_frame': 100 + index, 'time_s': index / 20,
                      'camera_png_sha256': {}}
                     for index in range(900)]
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            path = root / (camera + '.mkv')
            path.write_text('MOCK ONLY ' + camera + '\n')
            cameras[camera] = {'path': path.name, 'sha256': sha(path),
                               'frame_count': 900}
            archive_path = root / (camera + '.zip')
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_STORED) as archive:
                for index in range(900):
                    raw = b'\x89PNG\r\n\x1a\nMOCK ONLY ' + camera.encode() + str(index).encode()
                    archive.writestr(f'{index:04d}-{100 + index}.png', raw)
                    frame_map[index]['camera_png_sha256'][camera] = hashlib.sha256(raw).hexdigest()
            archives[camera] = {'path': archive_path.name, 'sha256': sha(archive_path)}
        frame_map_path = root / 'camera-frame-map.jsonl'
        frame_map_path.write_text(''.join(json.dumps(item) + '\n' for item in frame_map))
        (root / 'capture-identity.json').write_text(json.dumps({
            'case_id': case_id, 'source_kind': 'original_native_capture',
            'diagnostic_fixture': False, 'reviewed_site_sha256': reviewed['site_sha256'],
            'frames_sha256': sha(rows), 'cameras': cameras,
            'camera_frame_map_sha256': sha(frame_map_path),
            'camera_archives': archives}) + '\n')
        measurement = {'source_hashes': hashes,
                       'right_front_wheel_curb_upper_bound_m': 0.25}
        with patch('delivery_audit.verify', return_value=reviewed) as source_check, \
             patch('delivery_audit.measure_reviewed', return_value=measurement) as measure, \
             patch('delivery_audit.decode_camera', return_value={'frames': 900}) as decode:
            report = audit_attempt(root / 'mock-review.json', root, name)
            source_check.assert_called_once()
            measure.assert_called_once()
            if decode.call_count != 4 or report['source_hashes'] != hashes or \
               report['legal_status'] != 'unresolved' or report['physical_acceptance'] is not False:
                raise ValueError('mock-only original audit wiring changed')
    return 'mock-only original delivery audit wiring passed: ' + case_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-missing-review', action='store_true')
    args = parser.parse_args()
    try:
        print(probe(args.case, args.negative_missing_review))
    except ValueError as error:
        print(str(error))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
