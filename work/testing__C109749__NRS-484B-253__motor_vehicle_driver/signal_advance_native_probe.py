"""Native-lazy placement and control for measured signal-distance contrasts.

This plans an approach and commands the indicator after an observed warmup leg.
Only retained original motion and indicator readback can establish the actual
distance. District classification and legal signal sufficiency are unresolved.
"""
import math

from advance_signal_setup import upstream_waypoint

PROBES_M = (25.0, 30.48, 36.0, 86.0, 91.44, 97.0)


def prepare_probe(selected, *, target_signal_m, onset_margin_m=8.0):
    """Return an ego-upstream selection with a planned indicator onset leg.

    `approach_length_m` is an authored Native waypoint estimate. The source
    audit later measures the actual body path and may reject the target.
    """
    if target_signal_m not in PROBES_M:
        raise ValueError('Select a declared below/at/above signal probe')
    if (type(onset_margin_m) not in (int, float) or
            not math.isfinite(onset_margin_m) or onset_margin_m <= 0):
        raise ValueError('Positive finite onset margin required')
    ego = selected.get('ego', {})
    outside = ego.get('outside')
    existing = ego.get('approach_length_m')
    if (outside is None or type(existing) not in (int, float) or
            not math.isfinite(existing) or existing <= 0):
        raise ValueError('Sourced inbound ego approach required')
    planned = max(existing, target_signal_m + onset_margin_m)
    extra = planned - existing
    replacement = upstream_waypoint(outside, additional_m=extra) if extra > 0 else outside
    result = dict(selected)
    result['ego'] = dict(ego, outside=replacement, approach_length_m=planned)
    result['signal_probe'] = {
        'target_signal_distance_m': target_signal_m,
        'planned_total_approach_m': planned,
        'planned_indicator_onset_after_m': planned - target_signal_m,
        'existing_waypoint_approach_m': existing,
        'upstream_waypoint_extra_m': extra,
        'source_requirement': 'NRS 484B.413(2) numeric probe only',
        'actual_motion_and_signal_unverified': True,
        'district_classification': 'unresolved',
        'legal_verdict_asserted': False,
    }
    return result


class AdvanceIndicatorPolicy:
    """Latch an authored indicator after observed ego path travel from capture start."""

    def __init__(self, *, onset_after_m, enabled=True):
        if (type(onset_after_m) not in (int, float) or
                not math.isfinite(onset_after_m) or onset_after_m <= 0):
            raise ValueError('Positive finite indicator onset leg required')
        if type(enabled) is not bool:
            raise ValueError('Boolean indicator policy required')
        self.onset_after_m = onset_after_m
        self.enabled = enabled
        self.path_m = 0.0
        self.previous = None
        self.latched = False

    def step(self, *, ego_position_xy_m, turn_state):
        xy = ego_position_xy_m
        if (not isinstance(xy, (tuple, list)) or len(xy) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in xy)):
            raise ValueError('Original finite ego XY readback required')
        if turn_state not in ('approach', 'yield', 'turn', 'complete'):
            raise ValueError('Known turn-controller state required')
        if self.previous is not None:
            step = math.dist(self.previous, xy)
            if step > 5.0:
                raise ValueError('Ego position jump invalidates indicator path estimate')
            self.path_m += step
        self.previous = tuple(xy)
        if not self.enabled:
            return False
        if not self.latched and self.path_m >= self.onset_after_m:
            self.latched = True
        if turn_state in ('turn', 'complete') and not self.latched:
            raise ValueError('Subject turn precedes planned signal onset')
        return self.latched


def set_native_indicator(actor, carla, active):
    """Apply the commanded signal through the real actor API, then read back."""
    if type(active) is not bool:
        raise ValueError('Boolean indicator command required')
    state = carla.VehicleLightState.LeftBlinker if active else carla.VehicleLightState.NONE
    actor.set_light_state(state)
    actual = actor.get_light_state()
    if bool(actual & carla.VehicleLightState.LeftBlinker) != active:
        raise ValueError('Native left-indicator readback disagrees with command')
    return active
