"""Heavy-vehicle flashing-yellow scene request and source-shaped observation.

An adapter must implement these creation/readback operations in the Native runner.
The chosen speeds and blink period are engineering inputs, not legal thresholds.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot

@dataclass(frozen=True)
class Case:
    name: str
    direction: str
    target_mps: float
    crossing_vehicle: bool

CASES={
    'east_cautious_proxy':Case('east_cautious_proxy','east',3.0,True),
    'east_faster_proxy':Case('east_faster_proxy','east',7.0,True),
    'east_no_crossing':Case('east_no_crossing','east',3.0,False),
    'west_cautious_proxy':Case('west_cautious_proxy','west',3.0,True),
}

def lamp_on(time_s,cycle_s=.5):
    if time_s<0 or cycle_s<=0:raise ValueError('invalid lamp timing')
    return time_s%cycle_s<cycle_s/2

def construct(adapter,case):
    if case.direction not in ('east','west'):raise ValueError('unsupported approach direction')
    intersection=adapter.intersection(layout='blind_intersection',through_lanes=2,cross_lanes=2)
    sign=-1 if case.direction=='east' else 1
    start,end=(sign*70.0,0.0),(-sign*70.0,0.0)
    head=adapter.signal_head(lens='yellow',illuminated=True,governs_approach=case.direction,
                             mounted_xy=(sign*12.0,-sign*3.0))
    device=adapter.official_control_device(type='flashing_yellow',linked_signal=head)
    ego=adapter.vehicle(role='ego',vehicle_class='heavy_vehicle',route=[start,end],target_mps=case.target_mps)
    crossing=None
    if case.crossing_vehicle:
        crossing=adapter.vehicle(role='crossing',vehicle_class='motor_vehicle',route=[(0,-65),(0,65)],target_mps=5)
    return {'intersection':intersection,'signal_head':head,'official_device':device,'ego':ego,'crossing':crossing}

def measure(samples):
    if len(samples)<10:raise ValueError('at least ten original 20 Hz samples required')
    rows=[]
    for i,s in enumerate(samples):
        if abs(s.get('time_s',-1)-i*.05)>.005:raise ValueError('non-20Hz original time')
        if s.get('signal_head_visible') is not True or type(s.get('yellow_lens_on')) is not bool:
            raise ValueError('missing physical yellow signal readback')
        if not s.get('official_device_source') or not s.get('signal_source') or not s.get('ego_source'):
            raise ValueError('original device, signal or heavy-vehicle source missing')
        if s.get('ego_vehicle_class')!='heavy_vehicle' or s.get('approach_direction') not in ('east','west'):
            raise ValueError('heavy subject or approach direction missing')
        if type(s.get('ego_speed_mps')) not in (int,float) or s['ego_speed_mps']<0:
            raise ValueError('original speed sample missing')
        xy=s.get('ego_center_xy')
        if not isinstance(xy,list) or len(xy)!=2:raise ValueError('original ego position missing')
        rows.append({'time_s':s['time_s'],'speed_mps':s['ego_speed_mps'],
                     'distance_to_conflict_m':hypot(*xy),'yellow_lens_on':s['yellow_lens_on'],
                     'approach_direction':s['approach_direction'],
                     'crossing_present':bool(s.get('crossing_source'))})
    if set(r['yellow_lens_on'] for r in rows)!={False,True}:
        raise ValueError('intermittent yellow illumination not observed')
    if len(set(r['approach_direction'] for r in rows))!=1:raise ValueError('approach direction changed within case')
    return {'samples':rows,'vehicle_class':'heavy_vehicle','approach_direction':rows[0]['approach_direction'],
            'min_speed_mps':min(r['speed_mps'] for r in rows),'max_speed_mps':max(r['speed_mps'] for r in rows),
            'crossing_present':any(r['crossing_present'] for r in rows),'legal_caution_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('approach_speed','crossing_context','approach_direction'):
        raise ValueError('unknown comparison variable')
    if not a.get('samples') or not b.get('samples'):raise ValueError('original source measurements missing')
    for key in ('map_hash','signal_head_hash','official_device_source','blink_period_s','camera_plan_hash','duration_s','vehicle_class'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    var={'approach_speed':'target_mps','crossing_context':'crossing_vehicle','approach_direction':'direction'}[variable]
    for key in ('target_mps','crossing_vehicle','direction'):
        if key!=var and a.get(key)!=b.get(key):raise ValueError('undeclared condition changed: '+key)
    if a.get(var)==b.get(var):raise ValueError('deliberate comparison variable did not change')
    return {'comparison_complete':True,'variable':variable,'legal_caution_judgment':None}
