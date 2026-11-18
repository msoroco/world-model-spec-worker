"""Risk-triggered construction tunings shared by both C179480 primary cases."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tuning:
    candidate_id: str
    ego_spawn_longitudinal_m: float
    follower_spawn_longitudinal_m: float
    approach_speed_mps: float
    stop_radius_m: float
    follower_brake_gap_m: float
    risk_trigger: dict | None


TUNINGS = {
    'primary': Tuning('primary', -25., -48., 4., .8, 7., None),
    'fallback1': Tuning('fallback1', -35., -58., 4., .8, 7., {
        'source': 'Native spawn occupancy/actor collision readback',
        'metric': 'ego or follower spawn clearance',
        'failure_condition': 'primary spawn is occupied or starts in collision',
        'changed_knobs': ['ego_spawn_longitudinal_m',
                          'follower_spawn_longitudinal_m']}),
    'fallback2': Tuning('fallback2', -25., -48., 2.5, 1.25, 7., {
        'source': 'original ego stop position and velocity history',
        'metric': 'stop overshoot distance from surveyed target',
        'failure_condition': 'primary passes the stop target before a sampled complete stop',
        'changed_knobs': ['approach_speed_mps', 'stop_radius_m']}),
    'fallback3': Tuning('fallback3', -25., -65., 4., .8, 12., {
        'source': 'original follower speed, gap and collision history',
        'metric': 'following approach gap and contact',
        'failure_condition': 'primary follower closes below safe engineering gap or contacts ego',
        'changed_knobs': ['follower_spawn_longitudinal_m',
                          'follower_brake_gap_m']}),
}


def tuning(candidate_id):
    if candidate_id not in TUNINGS:
        raise ValueError('Unknown physical-risk candidate: '+str(candidate_id))
    selected = TUNINGS[candidate_id]
    if (selected.ego_spawn_longitudinal_m >= 0
            or selected.follower_spawn_longitudinal_m >=
            selected.ego_spawn_longitudinal_m
            or selected.approach_speed_mps <= 0
            or selected.stop_radius_m <= 0
            or selected.follower_brake_gap_m <= 0):
        raise ValueError('Invalid candidate actor/control geometry')
    return selected
