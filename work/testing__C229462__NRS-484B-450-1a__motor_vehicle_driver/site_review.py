"""Verify a reviewed original sidewalk site packet and its source bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidewalk_case import validate_site

ROLES = ('jurisdiction','highway_status','curb','lateral_highway_lines',
         'property_lines','pedestrian_use','map','sidewalk_polygon',
         'vehicle_blueprint','approach_route','parking_purpose',
         'exception_context','conflict_vehicle_motion',
         'target_overlap','target_touch','target_separate')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path,case_id):
    path=Path(path).resolve()
    site=json.loads(path.read_text(encoding='utf-8'))
    if (site.get('format')!='c229462-reviewed-original-sidewalk-v1' or
            site.get('source_kind')!='original_reviewed' or
            site.get('diagnostic_fixture') is not False or
            site.get('case_id')!=case_id or not site.get('reviewer')):
        raise ValueError('reviewed original sidewalk site identity missing')
    sources=site.get('sources')
    if not isinstance(sources,dict):raise ValueError('reviewed sidewalk source inventory missing')
    for role in ROLES:
        item=sources.get(role)
        if not isinstance(item,dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed original source missing: '+role)
        candidate=path.parent/item['path'];source=candidate.resolve()
        if candidate.is_symlink() or not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError('reviewed source path escapes packet: '+role)
        if sha(source)!=item['sha256']:
            raise ValueError('reviewed original source hash differs: '+role)
    for role in ROLES[:13]:
        if site.get(role+'_source_sha256')!=sources[role]['sha256']:
            raise ValueError('sidewalk site/source binding differs: '+role)
    for relation in ('overlap','touch','separate'):
        if site.get('target_footprints',{}).get(relation,{}).get('source_sha256')!=sources['target_'+relation]['sha256']:
            raise ValueError('sidewalk target/source binding differs: '+relation)
    if not site.get('map_id') or not site.get('vehicle_blueprint_id') or not site.get('sidewalk_area_id'):
        raise ValueError('reviewed Native map, motor vehicle or sidewalk identity missing')
    if (site.get('exception_context',{}).get('traffic_conflict_necessity')=='unresolved' and
            not site.get('conflict_vehicle_blueprint_id')):
        raise ValueError('reviewed traffic vehicle blueprint missing')
    validate_site(site)
    return site
