"""Source-gated Native passenger-zone construction entry for local adapters."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from passenger_zone import CASES, build_case, validate_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed_site(manifest_path, site_path, exact_case_id):
    manifest_path, site_path = Path(manifest_path), Path(site_path)
    if not manifest_path.is_file() or not site_path.is_file() or manifest_path.is_symlink() or site_path.is_symlink():
        raise ValueError('reviewed original passenger-zone site source missing')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('source_kind') != 'reviewed_original_site' or
            manifest.get('diagnostic_fixture') is not False or not manifest.get('reviewer') or
            manifest.get('case_id') != exact_case_id):
        raise ValueError('reviewed original source identity missing')
    record = manifest.get('files', {}).get('site-context.json', {})
    if record.get('sha256') != sha(site_path):
        raise ValueError('original site source hash mismatch')
    site = json.loads(site_path.read_text())
    if (site.get('source_kind') != 'reviewed_original_site' or not site.get('reviewer') or
            not site.get('zone', {}).get('passenger_anchor_source_sha256')):
        raise ValueError('original site or passenger anchor source missing')
    return site


def construct(adapter, manifest_path, site_path, exact_case_id):
    prefix = Path(__file__).resolve().parent.name + '__'
    if not exact_case_id.startswith(prefix):
        raise ValueError('wrong exact case')
    name = exact_case_id.removeprefix(prefix)
    case = next((item for item in CASES if item.name == name), None)
    if case is None:
        raise ValueError('unknown exact case')
    site = load_reviewed_site(manifest_path, site_path, exact_case_id)
    validate_site(site, case)
    made = build_case(adapter, site, case)
    return {'case_id': exact_case_id, 'owned': made['owned'],
            'site_sha256': sha(site_path),
            'source_manifest_sha256': sha(manifest_path),
            'physical_status': 'unverified', 'legal_status': 'unresolved'}
