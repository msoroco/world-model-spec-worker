"""Load a locally reviewed Native site only when its original source files still match.

This binds legal designation and exception records to bytes; the content still
requires human review and does not by itself establish a legal conclusion.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROLES = {
    'map': 'map_sha256',
    'controlled_access_determination': 'legal_controlled_access_source_sha256',
    'public_highway_boundary': 'public_highway_boundary_source_sha256',
    'lane_markings': 'lane_marking_source_sha256',
    'travel_direction': 'direction_source_sha256',
    'paved_shoulder': 'shoulder_paved_source_sha256',
    'lawful_sign_inventory': 'sign_source_sha256',
    'vehicle_class': 'vehicle_class_source_sha256',
    'emergency_necessity': 'emergency_record_source_sha256',
    'subsection3_authorization': 'subsection3_authorization_source_sha256',
    'native_spawn': 'native_spawn_source_sha256',
    'camera_plan': 'camera_plan_sha256',
}


def load(path: Path) -> dict:
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    if not isinstance(site, dict) or not isinstance(site.get('source_refs'), list):
        raise ValueError('reviewed source inventory missing')
    refs = site['source_refs']
    by_role = {r.get('role'): r for r in refs if isinstance(r, dict)}
    if len(by_role) != len(refs) or not set(ROLES) <= set(by_role):
        raise ValueError('reviewed source role missing or duplicated')
    for role, field in ROLES.items():
        ref = by_role[role]
        rel = ref.get('path')
        if not isinstance(rel, str) or not rel:
            raise ValueError('reviewed source path missing: ' + role)
        source = (path.parent / rel).resolve()
        if not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError('reviewed source escaped or missing: ' + role)
        digest = sha256(source.read_bytes()).hexdigest()
        if digest != ref.get('sha256') or digest != site.get(field):
            raise ValueError('reviewed source hash changed: ' + role)
    if site.get('assignment_id') != 'testing__C3997__NRS-484B-587-2b__motor_vehicle_driver':
        raise ValueError('reviewed source assignment identity differs')
    if not isinstance(site.get('native_spawn'), dict) or not site['native_spawn'].get('blueprint_id'):
        raise ValueError('reviewed Native spawn missing')
    if len(site['native_spawn'].get('pose_xyz_ypr', ())) != 6:
        raise ValueError('reviewed Native spawn pose missing')
    if not all(type(site.get(name)) in (int,float) for name in (
            'left_marking_lateral_m','right_marking_lateral_m','shoulder_outer_lateral_m')):
        raise ValueError('reviewed lane boundary coordinates missing')
    for name, lane in site.get('lanes', {}).items():
        if lane.get('source_sha256') not in (site['map_sha256'], site['lane_marking_source_sha256']):
            raise ValueError('reviewed lane source not bound: ' + name)
    site['reviewed_site_sha256'] = sha256(path.read_bytes()).hexdigest()
    return site
