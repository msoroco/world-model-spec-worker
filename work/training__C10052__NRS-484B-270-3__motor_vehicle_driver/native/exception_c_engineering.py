"""Synthetic construction for NRS 484B.270(3)(c) traffic-conflict exception.

This measures a proposed conflict-avoidance maneuver. It cannot establish that
the statutory exception applied to an original Native recording.
"""
from __future__ import annotations

import math

FRAMES=480
RATE_HZ=20
BIKE_BOUNDS=(-15.0,-5.0,20.0,-3.0)
TRAVEL_BOUNDS=(-15.0,-2.5,20.0,-.5)
NAMES=('primary','fallback1','fallback2','fallback3')

def body(x,y,length=5.2,width=1.8):
    return [[round(x-length/2,4),round(y-width/2,4)],
            [round(x+length/2,4),round(y-width/2,4)],
            [round(x+length/2,4),round(y+width/2,4)],
            [round(x-length/2,4),round(y+width/2,4)]]

def bounds(poly):
    if len(poly)!=4 or any(len(point)!=2 or not all(math.isfinite(v) for v in point)
                            for point in poly):raise ValueError('Body polygon missing')
    x=[point[0] for point in poly];y=[point[1] for point in poly]
    return min(x),min(y),max(x),max(y)

def overlap(a,b):
    ax0,ay0,ax1,ay1=bounds(a)
    bx0,by0,bx1,by1=bounds(b)
    return max(0,min(ax1,bx1)-max(ax0,bx0))*max(0,min(ay1,by1)-max(ay0,by0))

def policy(response,candidate):
    if response not in ('avoid','no_conflict') or candidate not in NAMES:
        raise ValueError('Unknown exception C construction')
    return {'format':'c10052-exception-c-construction-v1',
            'case_suffix':'exception_c_'+response,'candidate_id':candidate,
            'response':response,'capture_frames':FRAMES,'rate_hz':RATE_HZ,
            'ego_start_x_m':-60.0 if candidate=='fallback1' else -50.0,
            'diversion_start_frame':130 if candidate=='fallback2' else 140,
            'reference_visibility_override':candidate=='fallback3',
            'source_kind':'synthetic_cpu_fixture','accepted':False}

def rows(response,candidate,*,remove_actor=False):
    p=policy(response,candidate)
    result=[]
    for i in range(FRAMES):
        x=p['ego_start_x_m']+.25*i
        if response=='avoid':
            start=p['diversion_start_frame']
            if i<start:y=-1.5
            elif i<start+20:y=-1.5-2.5*(i-start)/20
            elif i<=240:y=-4.0
            elif i<260:y=-4.0+2.5*(i-240)/20
            else:y=-1.5
        else:y=-1.5
        active=response=='avoid' and 165<=i<=235 and not remove_actor
        actor=body(0.0,-1.5,4.6,1.8) if active else []
        result.append({'native_frame':1000+i,'time_s':round(i/RATE_HZ,2),
            'ego_center_xy':[round(x,4),round(y,4)],'ego_body_xy':body(x,y),
            'conflict_actor_id':221 if active else None,
            'conflict_actor_body_xy':actor,
            'conflict_actor_active':active,
            'scripted_reference_visible':p['reference_visibility_override'] or i%10!=0,
            'synthetic_diagnostic':True})
    return result

def measure(samples,p):
    if len(samples)!=FRAMES or p['capture_frames']!=FRAMES:
        raise ValueError('Expected 480 source rows')
    if any(row['native_frame']!=1000+i or row['time_s']!=round(i/RATE_HZ,2)
           for i,row in enumerate(samples)):
        raise ValueError('Original frame/time join changed')
    active=[];bike=[];collisions=[];counterfactual=[]
    for i,row in enumerate(samples):
        ego=row['ego_body_xy'];bounds(ego)
        x,y=row['ego_center_xy']
        if row['conflict_actor_active']:
            if row['conflict_actor_id']!=221:raise ValueError('Actor identity changed')
            actor=row['conflict_actor_body_xy'];bounds(actor)
            active.append(i)
            if overlap(ego,actor)>.001:collisions.append(i)
            if overlap(body(x,-1.5),actor)>.001:counterfactual.append(i)
        elif row['conflict_actor_id'] is not None or row['conflict_actor_body_xy']:
            raise ValueError('Inactive actor retains body')
        if overlap(ego,[[-15,-5],[20,-5],[20,-3],[-15,-3]])>.001:bike.append(i)
    valid=(bool(active) and bool(counterfactual) and not collisions and bool(bike))
    if p['response']=='no_conflict':valid=(not active and not bike)
    return {'case_suffix':p['case_suffix'],'candidate_id':p['candidate_id'],
        'active_conflict_actor_frames':len(active),
        'counterfactual_straight_collision_frames':len(counterfactual),
        'actual_collision_frames':len(collisions),
        'bicycle_lane_occupied_frames':len(bike),
        'synthetic_avoidance_geometry':valid,
        'actor_original_native_verified':False,
        'legal_exception_verified':False,'accepted':False}

def triggers(samples,p):
    if len(samples)!=FRAMES:raise ValueError('Incomplete trigger source')
    first=samples[0]['ego_center_xy'][0]
    runway=round(0-first,3)
    bike=next((i for i,row in enumerate(samples)
               if row['ego_center_xy'][1]<-1.6),None)
    lead=None if bike is None else 165-bike
    fraction=round(sum(row['scripted_reference_visible'] is True for row in samples[165:236])/71,6)
    return {'case_suffix':p['case_suffix'],'candidate_id':p['candidate_id'],
        'approach_runway_m':runway,'diversion_lead_frames':lead,
        'scripted_reference_visible_fraction':fraction,
        'fallback1_trigger':runway<55,
        'fallback2_trigger':lead is not None and lead<25,
        'fallback3_trigger':fraction<.95,
        'original_camera_pixels_verified':False}
