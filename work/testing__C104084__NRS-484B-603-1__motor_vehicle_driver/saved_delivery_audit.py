"""Independent saved integrity pass over a published hill-crest bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_crest_audit import ASSIGNMENT, CAMERAS, PROFILES
from saved_crest_bundle import verify_bundle


EXPECTED_FILES = {'manifest.json', 'finalized.json', 'native-map.xodr',
                  'grade.json', 'motion.json', 'context.json', 'other-route.json',
                  'frame-map.jsonl', *(f'{name}.mkv' for name in CAMERAS)}


def audit(attempt, *, expected_case):
    root = Path(attempt)
    if not root.is_dir() or any(p.is_symlink() for p in root.iterdir()):
        raise ValueError('published saved attempt is absent or symlinked')
    if {p.name for p in root.iterdir()} != EXPECTED_FILES:
        raise ValueError('published saved source inventory differs')
    manifest_path = root / 'manifest.json'
    result_path = root / 'finalized.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if (expected_case not in {f'{ASSIGNMENT}__{name}' for name in PROFILES} or
            manifest.get('case_id') != expected_case or result.get('case_id') != expected_case):
        raise ValueError('published exact case differs')
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if result.get('source_manifest_sha256') != manifest_sha:
        raise ValueError('published finalizer manifest seal differs')
    recomputed = verify_bundle(root, manifest, expected_case=expected_case)
    recomputed['source_manifest_sha256'] = manifest_sha
    recomputed['native_map_sha256'] = manifest['native_map_sha256']
    recomputed['native_capture_ref'] = manifest['native_capture_ref']
    if result != recomputed:
        raise ValueError('published finalizer differs from original saved sources')
    if result['checks'].get('physical_completion') is not False or result['legal_verdict_claimed'] is not False:
        raise ValueError('unsupported physical or legal acceptance claim')
    return {'format': 'c104084-saved-delivery-integrity-v1',
            'case_id': expected_case, 'source_manifest_sha256': manifest_sha,
            'finalized_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
            'frame_count': recomputed['frame_count'],
            'decoded_camera_count': len(recomputed['camera_decodes']),
            'physical_acceptance': False, 'legal_judgment': 'unresolved'}
