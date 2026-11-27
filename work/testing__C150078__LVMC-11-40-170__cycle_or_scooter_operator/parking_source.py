"""Fail-closed admission of an original rack-parking site and episode.

The requested setup never counts as evidence. The local operator supplies reviewed
original packets and original Native observations; this module checks source joins.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'testing__C150078__LVMC-11-40-170__cycle_or_scooter_operator'
CASE_SPEC = {
    'bicycle_rack_clear': ('bicycle', 'sidewalk_rack', 'clear'),
    'bicycle_rack_narrow': ('bicycle', 'sidewalk_rack', 'narrow'),
    'electric_bicycle_rack': ('electric_bicycle', 'sidewalk_rack', 'clear'),
    'electric_scooter_rack': ('electric_scooter', 'sidewalk_rack', 'clear'),
    'bicycle_building': ('bicycle', 'sidewalk_building', 'clear'),
    'bicycle_sidewalk_curb': ('bicycle', 'sidewalk_curb', 'clear'),
    'bicycle_roadway_curb': ('bicycle', 'roadway_curb', 'clear'),
    'bicycle_other': ('bicycle', 'other_street_location', 'clear'),
}
REQUIRED = ('map','street','device','person','rack','sidewalk','curb','building','pedestrian_context','parking_history')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('finite xy point required')
    return tuple(float(v) for v in value)


def inside(value, vertices):
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError('reviewed polygon required')
    x,y=point(value)
    poly=[point(v) for v in vertices]
    hit=False
    for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
        if (ay>y)!=(by>y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            hit=not hit
    return hit


def reviewed_packet(root, ref, name):
    if not isinstance(ref,dict):
        raise ValueError('missing original source reference: '+name)
    rel=ref.get('path')
    if not isinstance(rel,str) or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError('contained original source path required: '+name)
    target=(root/rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file() or sha(target)!=ref.get('sha256'):
        raise ValueError('original source missing or changed: '+name)
    packet=json.loads(target.read_text())
    if packet.get('source_kind')!='reviewed_original' or not packet.get('review_source'):
        raise ValueError('original review source required: '+name)
    return packet


def load_site(path, case_id):
    path=Path(path).resolve()
    if not case_id.startswith(ASSIGNMENT+'__'):
        raise ValueError('wrong assignment')
    label=case_id[len(ASSIGNMENT)+2:]
    if label not in CASE_SPEC:
        raise ValueError('unsupported exact case')
    site=json.loads(path.read_text())
    if site.get('assignment_id')!=ASSIGNMENT or site.get('case_id')!=case_id:
        raise ValueError('wrong site case')
    if site.get('requested')!=dict(zip(('device_class','placement','pedestrian_context'),CASE_SPEC[label])):
        raise ValueError('site differs from exact case request')
    refs=site.get('sources')
    if not isinstance(refs,dict) or set(REQUIRED)-set(refs):
        raise ValueError('original site source inventory incomplete')
    records={name:reviewed_packet(path.parent,refs[name],name) for name in REQUIRED}
    street=records['street']
    if street.get('city_jurisdiction') is not True or street.get('public_vehicular_access') is not True or street.get('one_way_operation') is not True:
        raise ValueError('original City one-way street status required')
    if len(records['map'].get('opendrive_sha256',''))!=64 or not site.get('map_id'):
        raise ValueError('original map source required')
    device=records['device']
    if device.get('covered_class')!=CASE_SPEC[label][0] or not device.get('classification_basis') or not device.get('physical_identity'):
        raise ValueError('original covered-device classification required')
    person=records['person']
    if not person.get('responsible_person_identity') or person.get('parking_act_observed') is not True:
        raise ValueError('original responsible person and parking act required')
    if records['rack'].get('supports_device') is not True or not records['rack'].get('rack_extent_polygon_xy'):
        raise ValueError('original supporting rack required')
    target=site.get('target_xy')
    point(target)
    if not inside(target,records['street'].get('street_extent_polygon_xy')):
        raise ValueError('parking target outside original street')
    if CASE_SPEC[label][1].startswith('sidewalk') and not inside(target,records['sidewalk'].get('extent_polygon_xy')):
        raise ValueError('sidewalk target outside original boundary')
    if CASE_SPEC[label][1]=='roadway_curb' and not inside(target,records['street'].get('roadway_polygon_xy')):
        raise ValueError('roadway target outside original boundary')
    if not records['curb'].get('curb_line_xy') or not records['building'].get('facade_line_xy'):
        raise ValueError('original curb and building alternatives required')
    if not isinstance(records['pedestrian_context'].get('available_passing_routes'),list) or not records['pedestrian_context']['available_passing_routes']:
        raise ValueError('original pedestrian passage alternatives required')
    if not records['parking_history'].get('complete_window') or not records['parking_history'].get('identity_join'):
        raise ValueError('complete original parking history required')
    return site,records
