"""Source-bound motorcycle stop, two signal cycles and right-turn measurements."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

RATE_HZ=20
FRAMES=480
STOP_LINE_Y_M=-14.0
BODY_FRONT_M=1.25

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
    last_cross_traffic=None
    complete_cycles=0
    previous_cross_state=None
    second_cycle_frame=None
    for index,row in enumerate(frames):
        if row.get('frame')!=index or row.get('video_frame')!=index or row.get('native_frame')!=index:
            raise ValueError('Video/Native frame join differs')
        if abs(row.get('time_s',-100)-index/RATE_HZ)>1e-8:
            raise ValueError('Frame timestamp differs')
        if row.get('signal_state')!='steady_red' or row.get('signal_governs_ego') is not True:
            raise ValueError('Steady red governing signal is missing')
        if row.get('actor_blueprint')!='vehicle.kawasaki.ninja':
            raise ValueError('Qualified motorcycle actor source is missing')
        if row.get('turn_prohibition_present') is not False:
            raise ValueError('Turn prohibition survey is missing or positive')
        if row.get('fault_injection_command')!='withhold_motorcycle_detector_request':
            raise ValueError('Declared detector nonresponse command is missing')
        state=row.get('cross_signal_state')
        if state not in ('green','yellow','red'):
            raise ValueError('Cross-signal phase source missing')
        if previous_cross_state is not None and state!=previous_cross_state:
            if (previous_cross_state,state) not in (('green','yellow'),('yellow','red'),('red','green')):
                raise ValueError('Cross-signal phase order differs')
            if previous_cross_state=='red' and state=='green':
                complete_cycles+=1
                if complete_cycles==2:second_cycle_frame=index
        previous_cross_state=state
        if row.get('declared_complete_cycles')!=complete_cycles:
            raise ValueError('Declared signal-cycle count differs from observed states')
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
        if row.get('cross_traffic_conflict_occupied') is True:
            last_cross_traffic=index
        if row.get('ego_turn_entered') is True and turn_entry is None:
            turn_entry=index
            cycles_at_entry=complete_cycles
    if first_cross is None or turn_entry is None or last_ped is None or last_cross_traffic is None:
        raise ValueError('Missing crossing, turn, pedestrian or traffic conflict observation')
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
    if not stopped or turn_entry<=max(last_ped,last_cross_traffic):
        raise ValueError('Motorcycle stop or conflict yield absent')
    result={'source_sha256':expected_sha256,'source_kind':record['source_kind'],
            'case':record.get('case'),'frames':FRAMES,'rate_hz':RATE_HZ,
            'steady_red_frames':FRAMES,'first_front_stop_line_crossing_frame':first_cross,
            'pre_crossing_stationary_frames_contiguous':longest,
            'full_halt_before_right_turn':stopped,
            'complete_cross_signal_cycles_before_turn':cycles_at_entry,
            'second_complete_cycle_frame':second_cycle_frame,
            'two_complete_signal_cycles_waited_before_right_turn':cycles_at_entry>=2,
            'turn_entry_frame':turn_entry,'last_pedestrian_conflict_frame':last_ped,
            'last_cross_traffic_conflict_frame':last_cross_traffic,
            'minimum_yield_clearance_s':round((turn_entry-max(last_ped,last_cross_traffic))/RATE_HZ,3),
            'qualified_motorcycle_and_no_turn_prohibition_in_source':True,
            'injected_detector_nonresponse_command_in_source':True,
            'failed_detection_physical_causation_observed':False,
            'legal_verdict':None,
            'physical_behavior_observed':record['source_kind']=='original_native_and_video'}
    return result

def synthetic(case: str) -> dict:
    if case not in ('condition_a','condition_b'):
        raise ValueError('Unknown case')
    rows=[]
    for f in range(FRAMES):
        release=260 if case=='condition_a' else 140
        turn=301 if case=='condition_a' else 181
        if f<60:
            y=-40+23*f/59
            speed=23/59*RATE_HZ
        elif f<release:
            y=-17.0;speed=0.0
        elif f<release+40:
            y=-17+10*(f-release)/40;speed=5.0
        elif f<turn:
            y=-7.0
            speed=0.0
        elif f<=turn+60:
            theta=math.pi-(f-turn)*math.pi/120
            y=-7+5.25*math.sin(theta)
            speed=5.25*math.pi/120*RATE_HZ
        else:
            y=-1.75
            speed=2.0
        if f<turn:
            x=1.75
        elif f<=turn+60:
            theta=math.pi-(f-turn)*math.pi/120
            x=7+5.25*math.cos(theta)
        else:
            x=7+(f-turn-60)*.1
        phase=f%120
        cross='green' if phase<80 else 'yellow' if phase<100 else 'red'
        rows.append({'frame':f,'video_frame':f,'native_frame':f,'time_s':f/RATE_HZ,
                     'ego_x_m':round(x,6),
                     'ego_y_m':round(y,6),'ego_speed_m_s':speed,
                     'signal_state':'steady_red','signal_governs_ego':True,
                     'cross_signal_state':cross,'declared_complete_cycles':f//120,
                     'fault_injection_command':'withhold_motorcycle_detector_request',
                     'actor_blueprint':'vehicle.kawasaki.ninja',
                     'turn_prohibition_present':False,
                     'approach_lane':'extreme_right','intersecting_road':'two_way',
                     'pedestrian_conflict_occupied':140<=f<=160,
                     'cross_traffic_conflict_occupied':130<=f<=160,
                     'ego_turn_entered':f>=turn})
    return {'source_kind':'synthetic_cpu','case':case,'law_id':'NRS-484B-307-8d',
            'cell_id':'C110919','scope':'CPU timing and saved-path logic only; no CARLA or original pixels',
            'frames':rows}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for case in ('condition_a','condition_b'):
        path=args.output/f'{case}-480.json'
        path.write_text(json.dumps(synthetic(case),separators=(',',':'))+'\n')
        print(json.dumps(measure(path,sha256(path))))
