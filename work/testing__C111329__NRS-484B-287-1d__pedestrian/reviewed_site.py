"""Verify original map and pedestrian-device sources before Native construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_crossing import crossing_plan


def _read(root: Path, ref: dict) -> dict:
    rel = ref.get('path') if isinstance(ref, dict) else None
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError('original site source path missing or unsafe')
    candidate = root / rel
    if candidate.is_symlink():
        raise ValueError('original site source symlinked')
    path = candidate.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('original site source escapes attempt')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError('original site source hash mismatch')
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get('diagnostic') is not False:
        raise ValueError('original site source must be independently reviewed')
    return value


def verify(root: Path, site: dict, route_kind: str, authorization: bool) -> dict:
    """Reject a site whose measured geometry or device instruction is unbound.

    This proves only source consistency; it does not prove legal status or pixels.
    """
    root = Path(root).resolve(strict=True)
    if site.get('cell_id') != 'C111329' or site.get('actor') != 'pedestrian':
        raise ValueError('original site identity mismatch')
    refs = site.get('original_sources')
    if not isinstance(refs, dict) or set(refs) != {'map', 'devices'}:
        raise ValueError('original map and device sources required')
    map_source = _read(root, refs['map'])
    device_source = _read(root, refs['devices'])
    if (map_source.get('map_name') != site.get('map_name') or
            map_source.get('map_sha256') != site.get('map_sha256') or
            map_source.get('intersection_polygon') != site.get('intersection_polygon') or
            map_source.get('corners') != site.get('corners') or
            map_source.get('cell_id') != 'C111329'):
        raise ValueError('original map intersection or corner survey differs')
    if (device_source.get('map_sha256') != site.get('map_sha256') or
            device_source.get('devices') != site.get('devices') or
            device_source.get('cell_id') != 'C111329'):
        raise ValueError('original official pedestrian device survey differs')
    for item in site['devices']:
        if not item.get('official_source') or not item.get('instruction_source'):
            raise ValueError('official pedestrian device provenance absent')
        if not isinstance(item.get('pedestrian_governance'), str):
            raise ValueError('pedestrian-specific device governance absent')
    plan = crossing_plan(site, route_kind, authorization)
    if authorization and not any(
        d.get('id') in plan['authorizing_device_ids'] and
        d.get('diagonal_instruction_reviewed') is True
        for d in device_source['devices']
    ):
        raise ValueError('reviewed diagonal pedestrian instruction absent')
    return {'site_source_sha256': refs['map']['sha256'],
            'device_source_sha256': refs['devices']['sha256'],
            'route_kind': route_kind, 'authorization_requested': authorization,
            'exception_484B_290': 'unresolved'}
