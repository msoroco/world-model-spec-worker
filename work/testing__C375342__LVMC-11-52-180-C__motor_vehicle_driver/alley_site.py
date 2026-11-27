"""Fail-closed original-site admission for the designated alley duration cases."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'testing__C375342__LVMC-11-52-180-C__motor_vehicle_driver'
SOURCE_NAMES = ('map', 'alley', 'designation', 'marking', 'other_parking_rules', 'vehicle', 'prior_history')
CASE_INTERVALS = {
    'continuous_29m': ((300, 2040),),
    'continuous_30m': ((300, 2100),),
    'continuous_31m': ((300, 2160),),
    'return_total_30m': ((300, 1260), (1860, 2700)),
    'return_total_31m': ((300, 1260), (1860, 2760)),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value)):
        raise ValueError('finite two-coordinate point required')
    return float(value[0]), float(value[1])


def inside(point_xy, vertices):
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError('reviewed designated extent polygon required')
    polygon = [point(v) for v in vertices]
    x, y = point_xy
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def load_site(path, case_id):
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    if site.get('assignment_id') != ASSIGNMENT or site.get('case_id') != case_id:
        raise ValueError('wrong exact alley-duration case')
    label = case_id.rsplit('__', 1)[-1]
    if not case_id.startswith(ASSIGNMENT + '__') or label not in CASE_INTERVALS:
        raise ValueError('unsupported exact alley-duration case')
    if tuple(tuple(x) for x in site.get('requested_intervals_s', [])) != CASE_INTERVALS[label]:
        raise ValueError('reviewed site differs from exact duration request')
    refs = site.get('sources')
    if not isinstance(refs, dict) or set(SOURCE_NAMES) - set(refs):
        raise ValueError('all original alley, designation and lawfulness source packets required')
    records = {}
    for name in SOURCE_NAMES:
        ref = refs[name]
        rel = ref.get('path') if isinstance(ref, dict) else None
        if not isinstance(rel, str) or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('contained relative original source path required: ' + name)
        target = (path.parent / rel).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or sha(target) != ref.get('sha256'):
            raise ValueError('original source missing or changed: ' + name)
        records[name] = json.loads(target.read_text())
    alley = records['alley']
    if (alley.get('jurisdiction') != 'city' or alley.get('alley_status') != 'reviewed_original' or
            alley.get('rear_access_function') is not True or alley.get('cul_de_sac_excluded') is not True or
            not alley.get('definition_source')):
        raise ValueError('original municipal alley definition and jurisdiction review required')
    designation = records['designation']
    marking = records['marking']
    if (designation.get('determining_office') != 'City Traffic Engineer' or
            designation.get('permission_status') != 'reviewed_original' or
            designation.get('angle_parking_permitted') is not True or not designation.get('source') or
            marking.get('marking_status') != 'reviewed_original' or
            marking.get('permission_indicated') is not True or not marking.get('content_review')):
        raise ValueError('original Engineer angle designation and indicated marking required')
    target = point(site.get('target_xy'))
    if not inside(target, alley.get('alley_extent_polygon_xy')) or not inside(target, designation.get('permission_extent_polygon_xy')) or not inside(target, marking.get('governed_space_polygon_xy')):
        raise ValueError('target outside original reviewed angle-parking extent')
    rules = records['other_parking_rules']
    if rules.get('review_status') != 'reviewed_original' or rules.get('otherwise_lawful') is not True or not rules.get('source'):
        raise ValueError('original review of all other applicable parking restrictions required')
    if records['prior_history'].get('status') != 'reviewed_original_not_parked' or not records['prior_history'].get('source'):
        raise ValueError('original preceding vehicle parking history required')
    relocation = point(site.get('relocation_xy'))
    if inside(relocation, alley.get('alley_extent_polygon_xy')) or inside(relocation, designation.get('permission_extent_polygon_xy')):
        raise ValueError('relocation station remains inside reviewed alley or designation')
    if not records['vehicle'].get('source') or records['vehicle'].get('identity_status') != 'reviewed_original':
        raise ValueError('original vehicle identity required')
    if not isinstance(records['map'].get('opendrive_sha256'), str) or len(records['map']['opendrive_sha256']) != 64:
        raise ValueError('original OpenDRIVE source required')
    if not isinstance(site.get('map_id'), str) or not isinstance(site.get('road_id'), int) or not site.get('vehicle_blueprint_id'):
        raise ValueError('Native map, road and vehicle identity required')
    if not marking.get('prop_blueprint_id') or not isinstance(marking.get('prop_pose'), dict):
        raise ValueError('reviewed physical angle-marking prop required')
    for key in ('approach_heading_degrees', 'target_heading_degrees'):
        value = site.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('finite ' + key + ' required')
    if math.dist(point(site.get('approach_xy')), target) < 8:
        raise ValueError('construction approach too short')
    return site, records
