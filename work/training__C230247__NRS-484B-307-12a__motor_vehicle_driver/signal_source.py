"""Fail-closed Native lane-control signal inventory and state acquisition.

A generic traffic-light Green state is not a downward green arrow. This module
requires an exact lane-control asset identity from the original world and keeps
physical pixels and official authority for independent local review.
"""
import hashlib
import math
import xml.etree.ElementTree as ET

SIGNAL_ID = 100


def _number(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Missing original ' + name) from exc
    if not math.isfinite(number):
        raise ValueError('Nonfinite original ' + name)
    return number


def map_inventory(native_opendrive):
    if not isinstance(native_opendrive, str) or not native_opendrive:
        raise ValueError('Native OpenDRIVE readback required')
    root = ET.fromstring(native_opendrive)
    roads = [road for road in root.findall('road') if road.get('id') == '1']
    if len(roads) != 1:
        raise ValueError('Original road identity differs')
    signal = next((s for s in roads[0].findall('signals/signal')
                   if s.get('id') == str(SIGNAL_ID)), None)
    if signal is None or signal.get('dynamic') != 'yes':
        raise ValueError('Original dynamic overhead signal absent')
    validity = signal.find('validity')
    if validity is None or validity.attrib != {'fromLane':'-1','toLane':'-1'}:
        raise ValueError('Original governed lane differs')
    if signal.get('orientation') != '+':
        raise ValueError('Original signal orientation differs')
    x = _number(signal.get('s'), 'signal longitudinal position')
    y = _number(signal.get('t'), 'signal lateral position')
    z = _number(signal.get('zOffset'), 'signal mount height')
    if not 0 < x < _number(roads[0].get('length'), 'road length') or not -3.5 < y < 0 or z < 4:
        raise ValueError('Original signal is not overhead of its governed lane')
    return {'id':SIGNAL_ID,'lane_id':-1,'mount_lane_id':-1,
            'mount_m':[x,y,z],'facing_yaw_deg':0.0,
            'authority_source':'map_signal_inventory','inventory_verified':True,
            'mount_source':'map_signal_transform',
            'opendrive_sha256':hashlib.sha256(native_opendrive.encode()).hexdigest(),
            'official_authority_review_pending':True}


def observed_state(native_actor, inventory):
    """Read the native arrow role and live state; never translate plain Green."""
    if inventory.get('id') != SIGNAL_ID or not inventory.get('opendrive_sha256'):
        raise ValueError('Map signal inventory missing')
    if native_actor is None or getattr(native_actor, 'type_id', None) != 'traffic.lane_control_signal':
        raise ValueError('Exact Native lane-control actor absent')
    attributes = getattr(native_actor, 'attributes', None)
    if not isinstance(attributes, dict) or attributes.get('opendrive_signal_id') != str(SIGNAL_ID):
        raise ValueError('Native actor is not bound to original map signal')
    if attributes.get('display_role') != 'downward_green_arrow':
        raise ValueError('Native asset is not a downward green-arrow display')
    if not hasattr(native_actor, 'get_state'):
        raise ValueError('Live Native indication readback absent')
    state = str(native_actor.get_state())
    if state not in ('green_down_arrow', 'red_x', 'dark'):
        raise ValueError('Unsupported or generic Native light state')
    return {'source':'native_signal_state','signal_id':SIGNAL_ID,
            'indication':state,'actor_id':native_actor.id,
            'asset_role_source':'native_actor_attributes',
            'official_authority_review_pending':True}
