"""Finalize a parked-headlamp Native attempt from its sealed original sources.

The finalizer does not infer beam emission, physical aim, parking legality or
image visibility. It constructs the saved acquisition inventory consumed by the
independent delivery auditor.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import ASSIGNMENT, EXPECTED_FRAMES, VIEWS, audit
from lamp_probe import CASE_MODES


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize_acquisition(attempt: Path, *, case_id: str,
                         allow_diagnostic: bool = False) -> dict:
    root = Path(attempt).resolve(strict=True)
    if case_id not in {ASSIGNMENT + '__' + mode for mode in CASE_MODES}:
        raise ValueError('unknown exact parked-headlamp case')
    source = root / 'native-source-receipt.json'
    if source.is_symlink() or not source.is_file():
        raise ValueError('sealed Native source receipt missing')
    receipt = json.loads(source.read_text(encoding='utf-8'))
    if (receipt.get('format') != 'parked-headlamp-native-source-v1' or
            receipt.get('case_id') != case_id or
            receipt.get('frame_count') != EXPECTED_FRAMES or
            receipt.get('requested_mode') != case_id.rsplit('__', 1)[-1] or
            receipt.get('physical_acceptance_claimed') is not False):
        raise ValueError('Native source receipt identity or duration mismatch')
    if receipt.get('diagnostic_site') is not allow_diagnostic:
        raise ValueError('Native site diagnostic provenance mismatch')
    media = receipt.get('original_camera_media')
    if not isinstance(media, dict) or set(media) != set(VIEWS):
        raise ValueError('four original camera media seals required')
    sealed = {}
    for view in VIEWS:
        item = media[view]
        if not isinstance(item, dict) or item.get('source_frame_count') != EXPECTED_FRAMES:
            raise ValueError('original camera source frame count incomplete')
        relative = item.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError('original camera source path invalid')
        source_path = root / relative
        if any(part in ('', '.', '..') for part in relative.split('/')) or source_path.is_symlink():
            raise ValueError('original camera source path invalid')
        path = source_path.resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('original camera source escapes Native attempt')
        if _sha(path) != item.get('sha256'):
            raise ValueError('original camera media hash mismatch')
        sealed[view] = dict(item)
    acquisition = root / 'acquisition.json'
    if acquisition.exists() or acquisition.is_symlink():
        raise ValueError('saved acquisition already exists')
    manifest = {'format': 'parked-headlamp-acquisition-v1',
                'case_id': case_id,
                'acquisition_kind': 'cpu_fixture' if allow_diagnostic else 'native',
                'physical_acceptance_claimed': False,
                'native_receipt': {'path': source.name, 'sha256': _sha(source)},
                'media': sealed}
    acquisition.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    try:
        observed = audit(root, acquisition, case_id=case_id,
                         allow_diagnostic=allow_diagnostic)
    except Exception:
        acquisition.unlink()
        raise
    return {'case_id': case_id, 'acquisition_sha256': _sha(acquisition),
            'delivery_audit': observed,
            'physical_acceptance_claimed': False}
