"""Close a source-reviewed Native attempt for independent delivery audit.

This only seals source bytes and measured history. It does not decode video,
assert physical completion, or decide legal expeditiousness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from passenger_zone import CASES, measure_history, validate_site
from saved_audit import audit_original_history

AID = 'testing__C150116__NRS-484B-503__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def finalize(attempt, case_id):
    attempt = Path(attempt).resolve()
    if not case_id.startswith(AID + '__'):
        raise ValueError('wrong exact passenger-zone case')
    short = case_id.removeprefix(AID + '__')
    case = next((item for item in CASES if item.name == short), None)
    if case is None:
        raise ValueError('unknown exact passenger-zone case')
    if not attempt.is_dir() or any((attempt / name).exists() for name in
                                   ('source-manifest.json', 'original-history.jsonl',
                                    'saved-seal.json', 'saved-result.json', 'capture-identity.json')):
        raise ValueError('original attempt absent or already finalized')
    capture = read(attempt / 'capture-seal.json')
    if (capture.get('case_id') != case_id or capture.get('provenance_kind') != 'native'
            or capture.get('diagnostic_fixture') is not False or capture.get('frames') != 900
            or capture.get('capture_rate_hz') != 20):
        raise ValueError('original 900-frame Native capture seal missing')
    for name, digest in capture.get('sources', {}).items():
        path = attempt / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or
                not path.is_file() or path.is_symlink() or sha(path) != digest):
            raise ValueError('original capture source changed: ' + name)
    reviewed_manifest = attempt / 'reviewed-site/source-manifest.json'
    reviewed_site = attempt / 'reviewed-site/site-context.json'
    if (sha(reviewed_manifest) != capture.get('reviewed_manifest_sha256') or
            sha(reviewed_site) != capture.get('reviewed_site_sha256')):
        raise ValueError('reviewed site source changed')
    packet = read(reviewed_manifest)
    provenance = packet.get('source_provenance', {})
    if (packet.get('source_kind') != 'reviewed_original_site' or
            packet.get('diagnostic_fixture') is not False or
            provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('citation') or not provenance.get('reviewer')):
        raise ValueError('reviewed original site provenance missing')
    site = read(reviewed_site)
    if site.get('source_kind') != 'reviewed_original_site':
        raise ValueError('reviewed original site missing')
    site['source_kind'] = 'original_native_capture'
    validate_site(site, case)
    rows = [json.loads(line) for line in (attempt / 'history.jsonl').read_text().splitlines()]
    measured = measure_history(rows, case, site)
    history = attempt / 'original-history.jsonl'
    shutil.copyfile(attempt / 'history.jsonl', history)
    site_path = attempt / 'site-context.json'
    write(site_path, site)
    independent = audit_original_history(history, sha(history), short,
                                         site['zone']['boundary_source_sha256'],
                                         site['regulations']['source_sha256'])
    if rows[0].get('camera_plan_sha256') is None:
        raise ValueError('original camera plan source missing')
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        if capture['sources'].get(path.name) != sha(path):
            raise ValueError('original camera source changed: ' + name)
    seal = {'case_id': short, 'site_sha256': sha(site_path),
            'original_history_sha256': sha(history), 'frame_count': 900,
            'physical_visibility_verified': False, 'legal_judgment': None}
    result = {'case_id': short, 'site_sha256': sha(site_path),
              'original_history_sha256': sha(history), 'measurement': measured,
              'delivery_audit': independent, 'legal_judgment': None,
              'physical_visibility_verified': False}
    seal_path, result_path = attempt / 'saved-seal.json', attempt / 'saved-result.json'
    write(seal_path, seal)
    write(result_path, result)
    sources = ['site-context.json', 'original-history.jsonl', 'saved-seal.json',
               'saved-result.json', *[name + '.mkv' for name in CAMERAS]]
    manifest = {'case_id': case_id, 'source_kind': 'original_native_capture',
                'diagnostic_fixture': False, 'reviewer': provenance['reviewer'],
                'reviewed_manifest_sha256': sha(reviewed_manifest),
                'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
                'files': {name: {'path': name, 'sha256': sha(attempt / name)} for name in sources}}
    manifest_path = attempt / 'source-manifest.json'
    write(manifest_path, manifest)
    identity = {'case_id': case_id, 'source_kind': 'original_native_capture',
                'diagnostic_fixture': False, 'source_manifest_sha256': sha(manifest_path),
                'cameras': {name: {'sha256': sha(attempt / (name + '.mkv')),
                                   'frame_count': 900} for name in CAMERAS}}
    write(attempt / 'capture-identity.json', identity)
    return {'case_id': case_id, 'source_manifest_sha256': sha(manifest_path),
            'original_history_sha256': sha(history), 'legal_judgment': None,
            'physical_visibility_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.case), sort_keys=True))


if __name__ == '__main__':
    main()
