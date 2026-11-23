"""Saved-only source join for the exact straight circular-green cases.

The caller supplies sealed, source-hashed site and original frame packets. This
produces observations for later review, never a statutory right-of-way verdict.
"""
from __future__ import annotations

import json

from native_scene import SourceError, measure_attempt, require, source

ASSIGNMENT = 'testing__C111125__NRS-484B-307-2a__motor_vehicle_driver'
CASES = {
    'green_clear': (None, None),
    'green_vehicle_present': ('motor_vehicle', 'intersection'),
    'green_pedestrian_present': ('pedestrian', 'adjacent_crosswalk'),
    'green_pedestrian_late': ('pedestrian', 'outside'),
}


def process_saved(packet, root):
    """Check a sealed attempt and report original exhibition/later occupancy.

    A packet references immutable source bytes within root. This is CPU
    preparation, so the returned flag does not claim physical acceptance.
    """
    require(packet.get('assignment_id') == ASSIGNMENT, 'wrong assignment')
    suffix = packet.get('case_suffix')
    require(suffix in CASES, 'unknown exact case')
    require(packet.get('case_id') == ASSIGNMENT + '__' + suffix, 'wrong exact case ID')
    require(packet.get('candidate') in ('primary', 'fallback1', 'fallback2'), 'candidate identity missing')
    require(packet.get('attempt_id') and packet.get('recording_id'), 'attempt identity missing')
    site_ref = packet['site_ref']
    event_ref = packet['event_ref']
    site = json.loads(source(site_ref, root).read_text(encoding='utf-8'))
    measured = measure_attempt(site, root, event_ref)
    duration = packet['duration_frames']
    require(isinstance(duration, int) and duration >= 3, 'duration frames missing')
    require(measured['frame_count'] == duration, 'original duration differs')
    require(measured['green_frames'] == duration, 'circular green alone not evidenced throughout')
    kind, region = CASES[suffix]
    users = measured['exhibition']['other_users']
    if kind is None:
        require(users == [], 'clear case occupied at exhibition')
    else:
        require(len(users) == 1, 'exactly one other user required at exhibition')
        require(users[0]['kind'] == kind and users[0]['region'] == region, 'other user differs at exhibition')
        require(users[0]['lawful_presence_source'], 'lawful-presence source missing')
    if suffix == 'green_pedestrian_late':
        require(any(
            any(u['id'] == users[0]['id'] and u['region'] == 'adjacent_crosswalk'
                for u in row['other_users'])
            for row in measured['records'][1:]
        ), 'late pedestrian never enters adjacent crosswalk')
    hashes = {ref['path']: ref['sha256'] for ref in site['original_sources']}
    fixed = {
        'map_sha256': hashes[site['map_source_path']],
        'signal_source_sha256': hashes[site['signal_source_path']],
        'route_source_sha256': hashes[site['route_source_path']],
        'crosswalk_source_sha256': hashes[site['crosswalk_source_path']],
        'camera_profile_sha256': packet['camera_profile_sha256'],
        'duration_frames': duration,
        'official_head_id': site['official_head_id'],
        'ego_approach_id': site['ego_approach_id'],
    }
    require(fixed['camera_profile_sha256'], 'camera profile source hash missing')
    return {
        'assignment_id': ASSIGNMENT,
        'case_id': packet['case_id'],
        'case_suffix': suffix,
        'candidate': packet['candidate'],
        'attempt_id': packet['attempt_id'],
        'recording_id': packet['recording_id'],
        'site_ref': site_ref,
        'event_ref': event_ref,
        **fixed,
        **measured,
        'physical_acceptance_claimed': False,
    }
