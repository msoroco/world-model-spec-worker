"""Exact caravan spacing construction targets; CPU math is not Native evidence.

The longitudinal coordinate increases with travel. The towing combination is
represented by the complete rigid body extent, not just its towing vehicle.
"""

from math import isfinite

RATE_HZ = 20
DURATION_S = 30
FRAMES = RATE_HZ * DURATION_S
GROUP_LENGTHS_M = {'lead': 4.5, 'ego_combination': 9.0, 'rear': 4.5}
ENTRANT_LENGTH_M = 6.0
GAP_TARGETS_M = {'probe_a': 30.0, 'probe_b': 8.0}
CANDIDATES = {'primary': 6.0, 'fallback1': 5.0}


def plan(case_suffix, candidate='primary'):
    if case_suffix not in GAP_TARGETS_M or candidate not in CANDIDATES:
        raise ValueError('Unknown exact caravan case or candidate')
    return {'case_suffix': case_suffix, 'candidate_id': candidate,
            'clear_gap_target_m': GAP_TARGETS_M[case_suffix],
            'group_speed_request_mps': CANDIDATES[candidate],
            'ordered_group': ['lead', 'ego_combination', 'rear'],
            'combination_length_m': GROUP_LENGTHS_M['ego_combination'],
            'potential_entrant_length_m': ENTRANT_LENGTH_M,
            'physical_success_claimed': False,
            'legal_sufficiency_claimed': False}


def commanded_centers(case_suffix, candidate, frame):
    """One common group command; only the declared gap changes between cases."""
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Frame outside 30-second source contract')
    p = plan(case_suffix, candidate)
    speed = p['group_speed_request_mps']
    gap = p['clear_gap_target_m']
    lead = 100.0 + speed * frame / RATE_HZ
    ego = lead - (GROUP_LENGTHS_M['lead'] + GROUP_LENGTHS_M['ego_combination']) / 2 - gap
    rear = ego - (GROUP_LENGTHS_M['ego_combination'] + GROUP_LENGTHS_M['rear']) / 2 - gap
    combination_front = ego + GROUP_LENGTHS_M['ego_combination'] / 2
    lead_rear = lead - GROUP_LENGTHS_M['lead'] / 2
    return {'lead': lead, 'ego_combination': ego, 'rear': rear,
            'potential_entrant': (combination_front + lead_rear) / 2}


def clear_spaces(centers, extents=GROUP_LENGTHS_M):
    """Compute both consecutive clearances from complete measured body extents."""
    if set(centers) != {'lead', 'ego_combination', 'rear', 'potential_entrant'}:
        raise ValueError('Original complete caravan inventory missing')
    if set(extents) != set(GROUP_LENGTHS_M) or any(not isfinite(v) or v <= 0 for v in extents.values()):
        raise ValueError('Original body extent missing or invalid')
    a = centers['lead'] - extents['lead']/2 - centers['ego_combination'] - extents['ego_combination']/2
    b = centers['ego_combination'] - extents['ego_combination']/2 - centers['rear'] - extents['rear']/2
    if min(a, b) < 0:
        raise ValueError('Original caravan bodies overlap or reverse')
    return {'lead_to_combination_m': a, 'combination_to_rear_m': b}


def apply_group_command(actors, vector_factory, case_suffix, candidate):
    """Set the same forward velocity on every observed caravan actor.

    `vector_factory` is injected so this command can be checked without CARLA.
    A Native caller must separately inspect realized trajectories and body bounds.
    """
    if set(actors) != {'lead', 'ego_combination', 'rear'}:
        raise ValueError('Commanded caravan inventory differs')
    speed = plan(case_suffix, candidate)['group_speed_request_mps']
    for actor in actors.values():
        actor.set_target_velocity(vector_factory(x=speed, y=0.0, z=0.0))


def check(case_suffix, candidate):
    p = plan(case_suffix, candidate)
    for frame in range(FRAMES):
        gaps = clear_spaces(commanded_centers(case_suffix, candidate, frame))
        if any(abs(value - p['clear_gap_target_m']) > 1e-8 for value in gaps.values()):
            raise AssertionError('Authored clear-space target drifted')
    return {'frames': FRAMES, 'rate_hz': RATE_HZ, 'case_suffix': case_suffix,
            'candidate_id': candidate, 'gap_target_m': p['clear_gap_target_m'],
            'group_speed_request_mps': p['group_speed_request_mps'],
            'group_command_tested': True, 'physical_success_claimed': False}
