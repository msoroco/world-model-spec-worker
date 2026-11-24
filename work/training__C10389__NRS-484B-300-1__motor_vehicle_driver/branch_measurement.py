"""Fail-closed original-source meter for signal and officer branch attempts."""
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def measure(attempt,case_kind,requested_condition):
    attempt=Path(attempt)
    if case_kind not in ('signal','officer'):
        raise ValueError('Unknown statutory branch measurement')
    if requested_condition not in (('red','green') if case_kind=='signal' else ('none','proceed')):
        raise ValueError('Unknown exact branch condition')
    report=read(attempt/'native-capture-report.json')
    if (report.get('error') is not None or report.get('observed_frames')!=600 or
            report.get('requested_frames')!=600 or not isinstance(report.get('restoration'),dict) or
            report['restoration'].get('restored') is not True):
        raise ValueError('Complete restored original Native attempt required')
    mapping=read(attempt/'native-map-readback.json')
    if mapping.get('source_kind')!='original_native' or not mapping.get('stop_landmark_verified'):
        raise ValueError('Original Native device map readback required')
    landmark=mapping['stop_landmark_readback']
    expected=('3892','1000001') if case_kind=='signal' else ('3891','206')
    if (landmark.get('id'),landmark.get('type'))!=expected or landmark.get('road_id')!=389 or abs(landmark.get('s_m',-1)-50)>0.5:
        raise ValueError('Observed device topology differs from branch')
    actors=[json.loads(line) for line in (attempt/'native-raw-actors.jsonl').read_text().splitlines()]
    frames=[json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    if len(actors)!=600 or len(frames)!=600:
        raise ValueError('Original actor/video window incomplete')
    stopped=0;crossings=0;signal_states=set();officer_frames=0
    for index,(actor,frame) in enumerate(zip(actors,frames)):
        if (actor.get('source_kind')!='original_native' or actor.get('frame')!=index or
                frame.get('video_frame')!=index or actor.get('native_frame')!=frame.get('native_frame') or
                abs(actor.get('time_s',-100)-frame.get('time_s',100))>1e-6):
            raise ValueError('Original actor/video frame join differs')
        ego=actor['ego'];body=ego['body_native_xyz_m']
        if len(body)!=8:raise ValueError('Original actor body incomplete')
        front=max(point[0] for point in body)
        if front<50 and ego['speed_mps']<0.1:stopped+=1
        if front>=50:crossings+=1
        if case_kind=='signal':
            state=actor.get('signal_state_observed')
            if state is None:raise ValueError('Signal state source absent')
            signal_states.add(state)
        elif requested_condition=='proceed':
            if actor.get('officer_actor') is None:raise ValueError('Requested officer actor source absent')
            officer_frames+=1
    if case_kind=='signal' and (len(signal_states)!=1 or requested_condition.lower() not in next(iter(signal_states)).lower()):
        raise ValueError('Observed Native signal aspect differs')
    return {'format':'c10389-branch-original-meter-v1','case_kind':case_kind,
            'requested_condition':requested_condition,'stopped_before_frames':stopped,
            'body_at_station_frames':crossings,'officer_actor_frames':officer_frames,
            'signal_states_observed':sorted(signal_states),'source_hashes':{
                name:sha(attempt/name) for name in ('native-capture-report.json','native-map-readback.json',
                    'native-raw-actors.jsonl','video_frames.jsonl')},
            'official_placement_verified':False,'police_authority_verified':False,
            'legal_verdict_claimed':False,'original_native_observed':True}
