"""Frame-bound red-right-turn measurements, including synthetic CPU fixtures."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

RATE_HZ=20
FRAMES=480
STOP_LINE_Y_M=-14.0
BODY_FRONT_M=2.6

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def measure(path: Path, expected_sha256: str) -> dict:
    if sha256(path)!=expected_sha256:
        raise ValueError('Source bytes differ')
    record=json.loads(path.read_text())
    if record.get('source_kind') not in ('synthetic_cpu','original_native_and_video'):
        raise ValueError('Unsupported source kind')
    frames=record.get('frames')
    if not isinstance(frames,list) or len(frames)!=FRAMES:
        raise ValueError('Requires exactly 480 consecutive frames')
    previous_front=None
    previous_xy=None
    previous_speed=None
    first_cross=None
    halt=[]
    turn_entry=None
    last_ped=None
    for index,row in enumerate(frames):
        if row.get('frame')!=index or row.get('video_frame')!=index or row.get('native_frame')!=index:
            raise ValueError('Video/Native frame join differs')
        if abs(row.get('time_s',-100)-index/RATE_HZ)>1e-8:
            raise ValueError('Frame timestamp differs')
        if row.get('signal_state')!='steady_red' or row.get('signal_governs_ego') is not True:
            raise ValueError('Steady red governing signal is missing')
        if row.get('approach_lane')!='extreme_right' or row.get('intersecting_road')!='two_way':
            raise ValueError('Right-turn permission context is missing')
        y=row.get('ego_y_m')
        x=row.get('ego_x_m')
        speed=row.get('ego_speed_m_s')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (x,y,speed)) or speed<0:
            raise ValueError('Missing measured pose or speed')
        if previous_xy is not None:
            delta=math.dist((x,y),previous_xy)
            if delta>max(speed,previous_speed)/RATE_HZ+.02:
                raise ValueError('Pose step exceeds measured speed')
        previous_xy=(x,y)
        previous_speed=speed
        front=y+BODY_FRONT_M
        if first_cross is None and previous_front is not None and previous_front<STOP_LINE_Y_M<=front:
            first_cross=index
        previous_front=front
        if speed<=.05 and front<STOP_LINE_Y_M:
            halt.append(index)
        if row.get('pedestrian_conflict_occupied') is True:
            last_ped=index
        if row.get('ego_turn_entered') is True and turn_entry is None:
            turn_entry=index
    if first_cross is None or turn_entry is None or last_ped is None:
        raise ValueError('Missing crossing, turn or pedestrian conflict observation')
    # A full halt requires >=0.5 s contiguous at or before the line, before first crossing.
    before=[f for f in halt if f<first_cross]
    longest=0
    current=0
    prior=-2
    for frame in before:
        current=current+1 if frame==prior+1 else 1
        longest=max(longest,current)
        prior=frame
    stopped=longest>=10
    if turn_entry<=last_ped:
        raise ValueError('Ego entered conflict before pedestrian cleared')
    result={'source_sha256':expected_sha256,'source_kind':record['source_kind'],
            'case':record.get('case'),'frames':FRAMES,'rate_hz':RATE_HZ,
            'steady_red_frames':FRAMES,'first_front_stop_line_crossing_frame':first_cross,
            'pre_crossing_stationary_frames_contiguous':longest,
            'halt_before_nearest_boundary':stopped,
            'turn_entry_frame':turn_entry,'last_pedestrian_conflict_frame':last_ped,
            'yield_clearance_s':round((turn_entry-last_ped)/RATE_HZ,3),
            'right_turn_permission_context_observed_in_source':True,
            'legal_verdict':None,
            'physical_behavior_observed':record['source_kind']=='original_native_and_video'}
    return result

def synthetic(case: str) -> dict:
    if case not in ('reference','contrast'):
        raise ValueError('Unknown case')
    rows=[]
    for f in range(FRAMES):
        if f<100:
            y=-40+23*f/99
            speed=23/99*RATE_HZ
        elif case=='reference' and f<130:
            y=-17.0
            speed=0.0
        elif case=='contrast' and f<130:
            y=-17+10*(f-100)/30
            speed=10/30*RATE_HZ
        elif f<170:
            y=-17+10*(f-130)/40 if case=='reference' else -7.0
            speed=5.0 if case=='reference' else 0.0
        elif f<181:
            y=-7.0
            speed=0.0
        elif f<=241:
            theta=math.pi-(f-181)*math.pi/120
            y=-7+5.25*math.sin(theta)
            speed=5.25*math.pi/120*RATE_HZ
        else:
            y=-1.75
            speed=2.0
        if f<181:
            x=1.75
        elif f<=241:
            theta=math.pi-(f-181)*math.pi/120
            x=7+5.25*math.cos(theta)
        else:
            x=7+(f-241)*.1
        rows.append({'frame':f,'video_frame':f,'native_frame':f,'time_s':f/RATE_HZ,
                     'ego_x_m':round(x,6),
                     'ego_y_m':round(y,6),'ego_speed_m_s':speed,
                     'signal_state':'steady_red','signal_governs_ego':True,
                     'approach_lane':'extreme_right','intersecting_road':'two_way',
                     'pedestrian_conflict_occupied':140<=f<=160,
                     'ego_turn_entered':f>=181})
    return {'source_kind':'synthetic_cpu','case':case,'law_id':'NRS-484B-307-8a',
            'cell_id':'C110919','scope':'CPU timing and saved-path logic only; no CARLA or original pixels',
            'frames':rows}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for case in ('reference','contrast'):
        path=args.output/f'{case}-480.json'
        path.write_text(json.dumps(synthetic(case),separators=(',',':'))+'\n')
        print(json.dumps(measure(path,sha256(path))))
