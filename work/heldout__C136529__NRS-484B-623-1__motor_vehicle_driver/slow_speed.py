"""CPU side of the narrow-road slow-speed comparison.

All speeds and separations here are engineering targets or observations.  No
value is a legal definition of 'normal and reasonable' or 'necessary'.
"""
from dataclasses import dataclass
from math import hypot

@dataclass(frozen=True)
class Case:
    name: str
    ego_target_mps: float
    follower_target_mps: float
    obstruction: bool = False
    regulatory_control: bool = False

CASES = {
    'flowing_reference': Case('flowing_reference', 8.0, 8.0),
    'slow_with_following_traffic': Case('slow_with_following_traffic', 3.0, 8.0),
    'slow_for_obstruction': Case('slow_for_obstruction', 3.0, 8.0, obstruction=True),
    'slow_under_control': Case('slow_under_control', 3.0, 8.0, regulatory_control=True),
}


def construct(adapter, case: Case):
    """Create the same narrow two-direction road and opposing approach for each case.

    The adapter owns CARLA calls; its CPU fake exercises all creation calls.
    A closure prop and control device are physical objects, not metadata flags.
    """
    road = adapter.narrow_road(length_m=160, lane_width_m=2.75, lanes=2,
                               centerline_x=0.0)
    ego = adapter.vehicle(role='ego', route=[(0.0, -65.0), (0.0, 65.0)],
                          target_mps=case.ego_target_mps)
    follower = adapter.vehicle(role='follower', route=[(0.0, -85.0), (0.0, 65.0)],
                               target_mps=case.follower_target_mps)
    opposing = adapter.vehicle(role='opposing', route=[(0.0, 65.0), (0.0, -65.0)],
                               target_mps=8.0)
    props = []
    if case.obstruction:
        props.append(adapter.prop(kind='parked_vehicle', center=(0.0, 5.0),
                                  extent=(1.1, 1.4, 0.6)))
    if case.regulatory_control:
        props.append(adapter.prop(kind='temporary_speed_control', center=(2.7, -35.0),
                                  extent=(0.4, 0.2, 1.8), displayed_mps=3.0))
    return {'road': road, 'ego': ego, 'follower': follower,
            'opposing': opposing, 'props': props}


def measure(samples):
    """Retain continuous histories and descriptive quantities, never a legal label.

    samples are synchronized 20 Hz records with measured positions, velocity,
    actor validity, and source references from saved capture.
    """
    if len(samples) < 2:
        raise ValueError('at least two synchronized samples required')
    times = [s['time_s'] for s in samples]
    if any(b <= a or abs((b-a)-0.05) > 0.005 for a,b in zip(times,times[1:])):
        raise ValueError('nonmonotonic or non-20Hz sample time')
    out=[]
    for s in samples:
        if not all(s.get(role+'_valid') is True for role in ('ego','follower','opposing')):
            raise ValueError('missing observed participant')
        ep=s['ego_xy']; fp=s['follower_xy']; op=s['opposing_xy']
        out.append({'time_s':s['time_s'], 'ego_speed_mps':s['ego_speed_mps'],
                    'follower_speed_mps':s['follower_speed_mps'],
                    'follower_gap_m':hypot(ep[0]-fp[0],ep[1]-fp[1]),
                    'opposing_distance_m':hypot(ep[0]-op[0],ep[1]-op[1]),
                    'obstruction_visible':s.get('obstruction_visible'),
                    'control_visible':s.get('control_visible'),
                    'source':s['source']})
    return {'samples':out,'duration_s':times[-1]-times[0],
            'minimum_follower_gap_m':min(x['follower_gap_m'] for x in out),
            'mean_ego_speed_mps':sum(x['ego_speed_mps'] for x in out)/len(out),
            'mean_follower_speed_mps':sum(x['follower_speed_mps'] for x in out)/len(out),
            'legal_judgment':'unresolved'}


def audit_comparison(left, right, deliberate_difference):
    """Reject unmeasured comparisons and undeclared geometry/control changes."""
    if not left.get('samples') or not right.get('samples'):
        raise ValueError('missing measured samples')
    for key in ('map_hash','lane_width_m','weather','camera_plan_hash','duration_s'):
        if left.get(key) is None or left.get(key) != right.get(key):
            raise ValueError('comparison fixed condition differs: '+key)
    changed={key for key in ('ego_target_mps','obstruction','regulatory_control')
             if left.get(key)!=right.get(key)}
    if changed != set(deliberate_difference):
        raise ValueError('undeclared or missing comparison difference')
    return {'checked_fixed_conditions':['map_hash','lane_width_m','weather',
                                        'camera_plan_hash','duration_s'],
            'measured_only':True,'legal_judgment':'unresolved'}
