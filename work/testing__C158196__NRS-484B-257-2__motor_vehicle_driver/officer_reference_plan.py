"""Validate six exact C158196 officer and stopping-reference constructions."""

import hashlib
import json
from pathlib import Path

from officer_direction import PREFIX, SUFFIXES
from site_source import inventory
from stopping_reference import from_authored_site


SITES = {
    'officer_controls_go': ('line-reference-site.xodr', 'stop_line'),
    'officer_controls_hold': ('line-reference-site.xodr', 'stop_line'),
    'officer_present_inactive': ('line-reference-site.xodr', 'stop_line'),
    'stop_line_reference': ('line-reference-site.xodr', 'stop_line'),
    'crosswalk_reference': ('crosswalk-reference-site.xodr', 'near_crosswalk'),
    'nearest_view_reference': ('nearest-view-reference-site.xodr', 'nearest_view'),
}


def validate(root):
    root = Path(root)
    plan = json.loads((root / 'officer-reference-plan.json').read_text())
    rows = plan.get('cases')
    if (plan.get('format') != 'c158196-officer-reference-construction-plan' or
            plan.get('assignment_id') != PREFIX[:-2] or
            plan.get('legal_visibility_review_pending') is not True or
            not isinstance(rows, list) or len(rows) != len(SITES)):
        raise ValueError('Exact officer/reference construction plan incomplete')
    if (set(plan.get('actor_blueprints', {})) != {'ego', 'other', 'officer'} or
            not all(plan['actor_blueprints'].values()) or
            set(plan.get('officer_pose', {})) != {'stop', 'go'} or
            not all(plan['officer_pose'].values()) or
            plan.get('camera_mounts_source') != 'config.json'):
        raise ValueError('Native officer actor or camera construction missing')
    found = {}
    for row in rows:
        case_id = row.get('case_id', '')
        if not isinstance(case_id, str) or not case_id.startswith(PREFIX):
            raise ValueError('Wrong exact officer/reference case')
        suffix = case_id[len(PREFIX):]
        if suffix not in SUFFIXES or suffix in found:
            raise ValueError('Unknown or duplicate officer/reference case')
        found[suffix] = row
        site_name, kind = SITES[suffix]
        site_path = root / site_name
        if (row.get('site_path') != site_name or
                row.get('site_sha256') != hashlib.sha256(site_path.read_bytes()).hexdigest() or
                from_authored_site(site_path)['kind'] != kind):
            raise ValueError('Exact authored officer/reference site differs')
        site = inventory(site_path)
        if (not site['all_entrances_inventoried'] or
                site['ego_lane_key'] != '158190:-1' or
                site['other_lane_key'] != '158194:-1' or
                row.get('ego_start_xy_m') != [-40.0, 1.8] or
                row.get('other_start_xy_m') != [1.8, -22.0] or
                row.get('rate_hz') != 20 or row.get('duration_s') != 30 or
                row.get('engineering_only') is not True):
            raise ValueError('Exact signed-junction motion construction differs')
        if suffix.startswith('officer_'):
            if row.get('officer_position_xyz_m') != [-3.0, -5.5, 0.5]:
                raise ValueError('Native officer placement differs')
        elif row.get('officer_position_xyz_m') is not None:
            raise ValueError('Reference-only case unexpectedly spawns officer')
        if row.get('officer_go_frame') != (300 if suffix == 'officer_controls_go' else None):
            raise ValueError('Exact officer direction phase differs')
        if (row.get('other_release_frame') != 90 or
                not isinstance(row.get('physical_risk'), str) or
                not row['physical_risk']):
            raise ValueError('Other actor phase or physical risk missing')
    if set(found) != set(SITES):
        raise ValueError('Officer/reference case coverage incomplete')
    return {'case_ids': [row['case_id'] for row in rows],
            'site_count': 3, 'physical_motion_verified': False,
            'legal_exception_judgment': 'unresolved'}
