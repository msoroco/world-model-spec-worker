"""Seal an observed Native crest capture into an immutable saved attempt.

The caller supplies original Native files. This module never generates motion or
camera pixels; its finalizer rejects missing joins and incomplete camera streams.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from saved_crest_audit import ASSIGNMENT, CAMERAS, PROFILES, _source
from saved_crest_finalizer import finalize


SOURCES = ('native_map_source', 'grade_source', 'motion_source', 'context_source',
           'other_route_source', 'frame_map_source')


def _copy_source(source, destination: Path, name: str) -> dict:
    path = Path(source)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'original {name} source file required')
    target = destination / name
    digest = hashlib.sha256()
    with path.open('rb') as original, target.open('xb') as sealed:
        for block in iter(lambda: original.read(1024 * 1024), b''):
            sealed.write(block)
            digest.update(block)
    return {'path': name, 'sha256': digest.hexdigest()}


def assemble(source_spec: dict, destination, *, expected_case: str) -> dict:
    """Copy original files and run full saved finalization before sealing receipt.

    The destination must be fresh. The source spec is an acquisition claim and
    is retained verbatim; it does not itself establish Native physical origin.
    """
    if not isinstance(source_spec, dict):
        raise ValueError('source specification required')
    profile = source_spec.get('profile')
    if profile not in PROFILES or expected_case != f'{ASSIGNMENT}__{profile}':
        raise ValueError('selected exact crest case differs')
    if source_spec.get('acquisition_kind') != 'original_native':
        raise ValueError('original Native source claim required')
    map_hash = source_spec.get('native_map_sha256')
    if (not isinstance(map_hash, str) or len(map_hash) != 64 or
            any(char not in '0123456789abcdef' for char in map_hash)):
        raise ValueError('loaded Native map hash required')
    if not isinstance(source_spec.get('native_capture_ref'), str) or not source_spec['native_capture_ref'].strip():
        raise ValueError('original Native capture reference required')
    paths = source_spec.get('sources')
    if not isinstance(paths, dict) or set(paths) != set(SOURCES):
        raise ValueError('all six original crest sources required')
    cameras = source_spec.get('cameras')
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError('four original camera files required')
    dimensions = source_spec.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='crest-bundle-', dir=destination.parent))
    try:
        result = _assemble_into(source_spec, root, expected_case, profile, map_hash, paths,
                                cameras, dimensions)
        root.rename(destination)
        return result
    finally:
        if root.exists():
            shutil.rmtree(root)


def _assemble_into(source_spec, root, expected_case, profile, map_hash, paths,
                   cameras, dimensions):
    manifest = {'case_id': expected_case, 'profile': profile,
                'acquisition_kind': 'original_native', 'duration_s': 45,
                'rate_hz': 20, 'approach_start_m': source_spec.get('approach_start_m'),
                'native_map_sha256': source_spec['native_map_sha256'],
                'native_capture_ref': source_spec['native_capture_ref'],
                'camera_dimensions': dimensions}
    filenames = {'native_map_source': 'native-map.xodr',
                 'grade_source': 'grade.json', 'motion_source': 'motion.json',
                 'context_source': 'context.json',
                 'other_route_source': 'other-route.json',
                 'frame_map_source': 'frame-map.jsonl'}
    for key in SOURCES:
        manifest[key] = _copy_source(paths[key], root, filenames[key])
    if manifest['native_map_source']['sha256'] != map_hash:
        raise ValueError('loaded Native map bytes differ from declared hash')
    manifest['camera_sources'] = {camera: _copy_source(cameras[camera], root, f'{camera}.mkv')
                                  for camera in CAMERAS}
    manifest_path = root / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    result = verify_bundle(root, manifest, expected_case=expected_case)
    result['source_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result['native_map_sha256'] = source_spec['native_map_sha256']
    result['native_capture_ref'] = source_spec['native_capture_ref']
    (root / 'finalized.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    return result


def verify_bundle(attempt, manifest: dict, *, expected_case: str) -> dict:
    """Recheck the retained loaded-map bytes before saved case finalization."""
    root = Path(attempt)
    _, actual_map_hash = _source(root, manifest.get('native_map_source'))
    if manifest.get('native_map_sha256') != actual_map_hash:
        raise ValueError('loaded Native map hash differs from retained source')
    return finalize(root, manifest, expected_case=expected_case)


def main():
    parser = argparse.ArgumentParser(description='Seal an original saved crest attempt')
    parser.add_argument('--spec', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    result = assemble(spec, args.destination, expected_case=args.case)
    print(json.dumps({'case_id': result['case_id'],
                      'source_manifest_sha256': result['source_manifest_sha256'],
                      'frame_count': result['frame_count']}))


if __name__ == '__main__':
    main()
