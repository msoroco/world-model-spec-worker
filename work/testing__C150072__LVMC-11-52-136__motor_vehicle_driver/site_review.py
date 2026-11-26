"""Verify an original reviewed access-aisle site packet and its source bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from access_aisle import validate_site

REQUIRED = ('jurisdiction', 'map', 'aisle_marking', 'adjacent_designated_space',
            'accessible_route', 'ingress_egress_design', 'vehicle_blueprint',
            'approach_route', 'target_aisle_full', 'target_aisle_partial',
            'target_adjacent_space', 'activity_plan')
OPTIONAL_SIGN = ('access_symbol', 'fine_wording', 'sign_bottom_height')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path: Path, expected_case_id: str) -> dict:
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding='utf-8'))
    if (site.get('format') != 'c150072-reviewed-original-aisle-v1' or
            site.get('source_kind') != 'original_reviewed' or
            site.get('diagnostic_fixture') is not False or
            site.get('case_id') != expected_case_id or not site.get('reviewer')):
        raise ValueError('reviewed original access-aisle identity missing')
    names = REQUIRED + (OPTIONAL_SIGN if site.get('designation_relies_on_135a') else ())
    sources = site.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('reviewed source inventory missing')
    for name in names:
        item = sources.get(name)
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed original source missing: ' + name)
        candidate = path.parent / item['path']
        source = candidate.resolve()
        if candidate.is_symlink() or not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError('reviewed source path missing or escapes packet: ' + name)
        if sha(source) != item['sha256']:
            raise ValueError('reviewed original source hash differs: ' + name)
    expected = {'jurisdiction_source_sha256': 'jurisdiction',
                'map_source_sha256': 'map',
                'aisle_marking_source_sha256': 'aisle_marking',
                'adjacent_designated_space_source_sha256': 'adjacent_designated_space',
                'accessible_route_source_sha256': 'accessible_route',
                'ingress_egress_design_source_sha256': 'ingress_egress_design',
                'vehicle_blueprint_source_sha256': 'vehicle_blueprint',
                'approach_route_source_sha256': 'approach_route'}
    for field, name in expected.items():
        if site.get(field) != sources[name]['sha256']:
            raise ValueError('access-aisle site/source binding differs: ' + field)
    for name in OPTIONAL_SIGN:
        if site.get('designation_relies_on_135a') and site.get(name + '_source_sha256') != sources[name]['sha256']:
            raise ValueError('access-aisle sign/source binding differs: ' + name)
    for name in ('aisle_full', 'aisle_partial', 'adjacent_space'):
        if site.get('target_footprints', {}).get(name, {}).get('source_sha256') != sources['target_' + name]['sha256']:
            raise ValueError('access-aisle target/source binding differs: ' + name)
    validate_site(site)
    return site
