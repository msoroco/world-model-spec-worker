"""Bind a C111304 site packet to the loaded world and reviewed access source.

This is a CPU-checkable boundary. It does not establish that a synthetic test
site is a real highway or public-access premises.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError('site source missing or redirected')
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('site source decode failed') from exc
    if not isinstance(result, dict):
        raise ValueError('site source object required')
    return result


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_world_site(world, site_path: Path, access_source_path: Path,
                    access_review_path: Path, camera_plan_path: Path, case,
                    *, allow_diagnostic: bool = False) -> dict:
    """Return a verified site for encounter.build_case and Native capture."""
    from encounter import CASES, validate_site

    if case not in CASES:
        raise ValueError('unknown exact case')
    site = _read_json(site_path)
    review = _read_json(access_review_path)
    camera_plan = _read_json(camera_plan_path)
    if not access_source_path.is_file() or access_source_path.is_symlink():
        raise ValueError('public-access source missing or redirected')
    if site.get('public_access_basis') != case.public_access_basis:
        raise ValueError('case public-access basis mismatch')
    if (review.get('site_id') != site.get('site_id') or
            review.get('public_access_basis') != site.get('public_access_basis') or
            review.get('source_sha256') != _sha(access_source_path) or
            site.get('public_access_source_sha256') != review['source_sha256'] or
            site.get('public_access_review_sha256') != _sha(access_review_path)):
        raise ValueError('public-access review/source join mismatch')
    if review.get('source_kind') != 'reviewed_original' and not (
        allow_diagnostic and review.get('source_kind') == 'synthetic_fixture'
    ):
        raise ValueError('reviewed original public-access source required')
    if review.get('source_kind') == 'reviewed_original' and not (
            review.get('reviewer') and review.get('source_citation') and
            review.get('reviewed_original_source') is True):
        raise ValueError('original public-access review incomplete')
    loaded_map = world.get_map()
    if loaded_map.name != site.get('map_name'):
        raise ValueError('loaded map name differs from site')
    map_source = loaded_map.to_opendrive()
    if not isinstance(map_source, str) or not map_source:
        raise ValueError('loaded OpenDRIVE source missing')
    map_hash = hashlib.sha256(map_source.encode('utf-8')).hexdigest()
    if map_hash != site.get('map_sha256'):
        raise ValueError('loaded OpenDRIVE hash differs from site')
    plan_source = json.dumps(camera_plan, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode('utf-8')
    plan_hash = hashlib.sha256(plan_source).hexdigest()
    if plan_hash != site.get('camera_plan_sha256'):
        raise ValueError('camera plan source hash mismatch')
    validate_site(site)
    bound = dict(site)
    bound['site_sha256'] = _sha(site_path)
    return bound
