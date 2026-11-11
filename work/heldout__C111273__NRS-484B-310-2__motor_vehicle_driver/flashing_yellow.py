"""CPU construction and observation for the flashing-yellow intersection.

The selected blink rate and approach speeds are engineering samples, not legal
interpretations of 'rapid' or 'with caution'. Official status is a sourced
premise and cannot be established by the lamp geometry alone.
"""
from dataclasses import dataclass
from math import hypot

@dataclass(frozen=True)
class Case:
    name: str
    approach_target_mps: float
    crossing_vehicle: bool
    direction: str

CASES={
 'east_cautious_approach':Case('east_cautious_approach',4.0,True,'east'),
 'east_faster_approach':Case('east_faster_approach',9.0,True,'east'),
 'east_clear_approach':Case('east_clear_approach',4.0,False,'east'),
 'west_cautious_approach':Case('west_cautious_approach',4.0,True,'west'),
}

def lamp_on(time_s, phase_s=0.0, cycle_s=0.5):
    """Engineering 2 Hz square wave; retained readback must verify realization."""
    if time_s < 0 or cycle_s <= 0:
        raise ValueError('invalid lamp timing')
    return ((time_s+phase_s)%cycle_s) < cycle_s/2


def construct(adapter, case):
    """Make an actual signal head and opposing intersection approaches."""
    if case.direction not in ('east','west'):
        raise ValueError('unsupported approach direction')
    intersection=adapter.intersection(through_lanes=2,cross_lanes=2)
    start=(-70.0,0.0) if case.direction=='east' else (70.0,0.0)
    end=(70.0,0.0) if case.direction=='east' else (-70.0,0.0)
    head=adapter.signal_head(lens='yellow', illuminated=True,
                             mounted_xy=(-12.0,-3.0) if case.direction=='east' else (12.0,3.0),
                             governs_approach=case.direction)
    device=adapter.official_control_device(type='intersection_advance_warning',
                                             linked_signal=head)
    ego=adapter.vehicle(role='ego',route=[start,end],target_mps=case.approach_target_mps)
    crossing=None
    if case.crossing_vehicle:
        crossing=adapter.vehicle(role='crossing',route=[(0.0,-65.0),(0.0,65.0)],
                                 target_mps=6.0)
    return {'intersection':intersection,'signal_head':head,'official_device':device,
            'ego':ego,'crossing':crossing}


def measure(samples):
    """Join physical lamp readback and participant trajectories at 20 Hz."""
    if len(samples)<2: raise ValueError('at least two original samples required')
    rows=[];last=None
    for s in samples:
        t=s['time_s']
        if last is not None and (t<=last or abs(t-last-.05)>.005):
            raise ValueError('non-20Hz original time')
        last=t
        if s.get('signal_head_visible') is not True or type(s.get('yellow_lens_on')) is not bool:
            raise ValueError('missing physical flashing-yellow readback')
        if not s.get('official_device_source'):
            raise ValueError('official-device premise lacks source')
        if not s.get('ego_valid'):
            raise ValueError('missing ego original state')
        distance=hypot(*s['ego_center_xy'])
        row={'time_s':t,'ego_speed_mps':s['ego_speed_mps'],
             'ego_center_distance_to_conflict_m':distance,
             'yellow_lens_on':s['yellow_lens_on'],
             'signal_head_visible':s['signal_head_visible'],
             'crossing_valid':s.get('crossing_valid') is True,
             'source':s['source']}
        if row['crossing_valid']:
            row['crossing_center_distance_to_conflict_m']=hypot(*s['crossing_center_xy'])
        rows.append(row)
    if len(set(x['yellow_lens_on'] for x in rows))<2:
        raise ValueError('no observed intermittent illumination')
    return {'samples':rows,'duration_s':rows[-1]['time_s']-rows[0]['time_s'],
            'legal_caution_judgment':'unresolved'}


def audit_comparison(a,b,differences):
    if not a.get('samples') or not b.get('samples'):
        raise ValueError('missing original measurements')
    for key in ('map_hash','signal_head_hash','official_device_source','blink_period_s',
                'camera_plan_hash','duration_s'):
        if a.get(key) is None or a.get(key)!=b.get(key):
            raise ValueError('fixed condition differs: '+key)
    changed={key for key in ('approach_target_mps','crossing_vehicle','direction')
             if a.get(key)!=b.get(key)}
    if changed!=set(differences):
        raise ValueError('undeclared or missing deliberate difference')
    return {'fixed_conditions_checked':True,'legal_caution_judgment':'unresolved'}
