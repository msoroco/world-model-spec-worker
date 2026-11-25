"""Check original rider identity, device inventory and conduct source packets.

The packets retain observations. They do not decide lawful riding, intention,
interference, or whether an unobserved device meets a statutory definition.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


KINDS = ('human_powered_bicycle', 'electric_bicycle', 'electric_scooter')


class RiderSourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RiderSourceError(message)


def source(root, ref):
    base = Path(root).resolve()
    require(isinstance(ref, dict) and isinstance(ref.get('path'), str)
            and isinstance(ref.get('sha256'), str), 'source reference missing')
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base) and path.is_file(), 'original rider source missing or escaping')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'],
            'original rider source hash mismatch')
    return path


def _finite_positive(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0, label + ' observation missing')


def verify_inventory(root, packet_ref, *, assignment_id, cell_id, blueprint_id, rider_kind):
    """Verify reviewed source references without accepting a legal verdict.

    The inventory and each cited source are independently hash bound. The
    original device and rule reviews must identify a reviewer and the actual
    source material; a blueprint label alone is not a classification source.
    """
    require(rider_kind in KINDS, 'unsupported rider kind')
    packet = json.loads(source(root, packet_ref).read_text(encoding='utf-8'))
    require(packet.get('assignment_id') == assignment_id and
            packet.get('cell_id') == cell_id, 'rider inventory assignment mismatch')
    require(packet.get('rider_kind') == rider_kind and
            packet.get('blueprint_id') == blueprint_id, 'rider inventory device mismatch')
    require(packet.get('lawful_riding_verdict') is None and
            packet.get('intent_verdict') is None and
            packet.get('interference_verdict') is None,
            'unsupported legal verdict in rider inventory')
    require(isinstance(packet.get('reviewer'), str) and packet['reviewer'].strip(),
            'rider inventory reviewer missing')
    sources = packet.get('original_sources')
    require(isinstance(sources, dict) and set(sources) ==
            {'device_review', 'rider_review', 'rules_review'},
            'device, rider and rules source reviews required')
    refs = list(sources.values())
    require(len({ref['path'] for ref in refs}) == 3, 'rider sources must be distinct')
    reviewed = {}
    asset_paths = set()
    for role, ref in sources.items():
        reviewed[role] = json.loads(source(root, ref).read_text(encoding='utf-8'))
        require(reviewed[role].get('reviewer') == packet['reviewer'] and
                reviewed[role].get('assignment_id') == assignment_id and
                reviewed[role].get('cell_id') == cell_id,
                role + ' review identity mismatch')
        asset_ref = reviewed[role].get('original_asset')
        require(isinstance(asset_ref, dict), role + ' original asset missing')
        source(root, asset_ref)
        asset_paths.add(asset_ref['path'])
    require(len(asset_paths) == 3, 'device, rider and rule original assets must be distinct')
    device = packet.get('device_observations')
    require(reviewed['device_review'].get('observations') == device,
            'device observations do not match reviewed source')
    require(isinstance(device, dict) and device.get('observed_blueprint_id') == blueprint_id,
            'reviewed blueprint observation mismatch')
    require(device.get('rendered_person_present') is True,
            'reviewed rider visual presence missing')
    if rider_kind == 'human_powered_bicycle':
        require(device.get('human_powered') is True and device.get('moped') is False,
                'human-powered bicycle classification missing')
        require(device.get('tandem_wheels') == 2, 'tandem wheel observation missing')
        _finite_positive(device.get('one_wheel_diameter_in'), 'wheel diameter')
        require(device['one_wheel_diameter_in'] > 14,
                'reviewed wheel diameter does not satisfy stated bicycle criterion')
    elif rider_kind == 'electric_bicycle':
        require(device.get('electric_drive_observed') is True and
                device.get('pedals_observed') is True,
                'electric bicycle drive and pedals observations missing')
        _finite_positive(device.get('motor_rating_w'), 'motor rating')
    else:
        require(device.get('electric_drive_observed') is True and
                device.get('standing_platform_observed') is True,
                'electric scooter drive and platform observations missing')
        _finite_positive(device.get('wheel_count'), 'wheel count')
    rider = packet.get('rider_observations')
    require(reviewed['rider_review'].get('observations') == rider,
            'rider observations do not match reviewed source')
    require(isinstance(rider, dict) and rider.get('distinct_from_ego') is True and
            rider.get('person_visible_in_review') is True,
            'distinct visible rider observation missing')
    rules = packet.get('rules_observations')
    require(reviewed['rules_review'].get('observations') == rules,
            'rules observations do not match reviewed source')
    require(isinstance(rules, dict) and rules.get('jurisdiction') == 'Nevada' and
            isinstance(rules.get('applicable_rules'), list) and rules['applicable_rules'] and
            isinstance(rules.get('conduct_sources'), list) and rules['conduct_sources'],
            'rider rules or conduct sources missing')
    for ref in rules['conduct_sources']:
        source(root, ref)
    return packet
