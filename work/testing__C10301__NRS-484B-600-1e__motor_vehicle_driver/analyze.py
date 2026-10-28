"""Saved original evidence audit and same-setting capability decision."""
import argparse
import hashlib
import json
import pathlib
import statistics
import sys


def runtime_audit():
    for parent in pathlib.Path(__file__).resolve().parents:
        package=parent/'runtime/main-pipeline-v1/scenario_pipeline'
        if package.is_dir():
            sys.path.insert(0,str(package))
            break
    from worker_exchange.media import audit
    return audit


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def first_entry_bracket(samples, role, boundary):
    for before,after in zip(samples,samples[1:]):
        actor_before=before[role];actor_after=after[role]
        if actor_before is None or actor_after is None:continue
        front_before=max(v[0] for v in actor_before['body_vertices_m'])
        front_after=max(v[0] for v in actor_after['body_vertices_m'])
        if front_before<boundary<=front_after:return [before['time_s'],after['time_s']]
    return None


def assess(attempt):
    attempt=pathlib.Path(attempt).resolve();cfg=json.loads((attempt/'config.json').read_text())
    case=cfg['case'];kind=cfg['mode'];samples=rows(attempt/'physical_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if not samples or len(samples)!=len(mapping):raise ValueError('Missing or mismatched original frame map')
    if any(m['native_frame']!=s['frame'] or m['carla_frame']!=s['frame'] or m['video_frame']!=i or m['time_s']!=s['time_s']
           for i,(s,m) in enumerate(zip(samples,mapping))):raise ValueError('Original frame/time join mismatch')
    if any(b['time_s']<=a['time_s'] for a,b in zip(samples,samples[1:])):raise ValueError('Nonmonotone original times')
    evidence=rows(attempt/'capture/evidence.jsonl')
    if len(evidence)!=len(samples) or any(e['original_frame']!=s['frame'] for e,s in zip(evidence,samples)):
        raise ValueError('Original evidence/source frame join mismatch')
    channel_counts={}
    for channel in case['recording_description']['channels']:
        name=channel['name'];data=rows(attempt/'channels'/(name+'.jsonl'))
        if len(data)!=len(samples) or any(row['value'] is None or row['time_s']!=s['time_s']
                                           for row,s in zip(data,samples)):
            raise ValueError('Missing or unjoined mandatory channel '+name)
        if name not in ('kin.speed','kin.velocity','kin.position','rel.surface_gap','env.wet_road','env.ice_or_snow','kin.time') and \
                any('original_observations' not in row['value'] for row in data):
            raise ValueError('Original source projection missing '+name)
        channel_counts[name]=len(data)
    audit=runtime_audit();mapping_sha=hashlib.sha256((attempt/'video_frames.jsonl').read_bytes()).hexdigest()
    checker_sha=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();video=[]
    for i in range(4):
        name='view%d'%i
        def source_pixels(frame, view=name):
            expected=mapping[frame.index]['source_frames'][view]
            if (frame.width,frame.height)!=(expected['width'],expected['height']):
                raise ValueError('Decoded source video dimensions differ')
            if hashlib.sha256(frame.pixels).hexdigest()!=expected['source_rgb_sha256']:
                raise ValueError('Decoded source video pixels differ from original sensor')
        receipt=audit(attempt/(name+'.mkv'),len(samples),checkers={'source_pixels':(checker_sha,source_pixels)},
                      mapping_sha256=mapping_sha,receipt=attempt/(name+'.source-decode.json'))
        video.append({'name':name,'frames':receipt['frames'],'dimensions':receipt['dimensions'],
                      'video_sha256':receipt['video_sha256'],'source_pixels_checked':True})
    setup=json.loads((attempt/'native-setup.json').read_text())
    measurements={'sample_count':len(samples),'window_s':[samples[0]['time_s'],samples[-1]['time_s']],
                  'channel_counts':channel_counts,'source_video':video,'native_road_ids':setup['native_road_ids']}
    issues=[]
    if kind=='following':
        gap_target=case['variable_assignments']['commanded_following_gap']['value']
        window=[s for s in samples if 15<=s['time_s']<=24 and s['surface_gap_m'] is not None]
        gaps=[s['surface_gap_m'] for s in window]
        measured=statistics.mean(gaps) if gaps else None
        time_gaps=[s['surface_gap_m']/s['ego']['speed_mps'] for s in window if s['ego']['speed_mps']>.1]
        measurements.update({'requested_gap_m':gap_target,'measured_gap_mean_m':measured,
            'measured_gap_min_m':min(gaps) if gaps else None,'time_gap_mean_s':statistics.mean(time_gaps) if time_gaps else None,
            'lane_change_completed':samples[-1]['ego']['position_m'][1]<-4.7,
            'wet_road_authored':cfg['authored_test_context'].get('wet_road')})
        if measured is None or abs(measured-gap_target)>2:issues.append('following gap target not measured within 2 m')
        if not measurements['lane_change_completed']:issues.append('lane change not observed')
    elif kind in ('absolute_speed','posted_speed'):
        target=case['variable_assignments']['commanded_approach_speed']['value']
        governed=[s for s in samples if kind=='absolute_speed' or s['ego']['position_m'][0]>=80]
        speeds=[s['ego']['speed_mps'] for s in governed]
        window=[s for s in governed if 15<=s['time_s']<=24]
        measured=statistics.mean(s['ego']['speed_mps'] for s in window) if window else None
        measurements.update({'requested_speed_mps':target,'measured_window_mean_mps':measured,
            'governed_full_trace_max_mps':max(speeds) if speeds else None,
            'governed_full_trace_max_mph':max(speeds)/.44704 if speeds else None,
            'governed_start_x_m':80 if kind=='posted_speed' else None,
            'governed_sample_count':len(governed),'native_landmarks':setup['native_landmarks']})
        if measured is None or abs(measured-target)>1:issues.append('actual target speed not measured within 1 m/s')
        if kind=='posted_speed' and not any(str(l['value'])=='25' for l in setup['native_landmarks']):
            issues.append('native posted-speed landmark absent')
    elif kind=='yellow_red':
        sequence=[]
        for s in samples:
            states=tuple(d['state'] for d in s['signal_devices'])
            if states and (not sequence or states!=sequence[-1]['states']):
                sequence.append({'time_s':s['time_s'],'states':states})
        entry=first_entry_bracket(samples,'ego',-7)
        entry_state=None if entry is None else next((s['signal_devices'][0]['state'] for s in samples
            if s['time_s']>=entry[1] and s['signal_devices']),None)
        measurements.update({'state_sequence':sequence,'body_front_entry_bracket_s':entry,
            'entry_signal_state':entry_state,'requested_obey_red':case['variable_assignments']['obey_red']['value']})
        if not sequence or not all(any(name in str(z['states']) for z in sequence) for name in ('Green','Yellow','Red')):
            issues.append('native green-yellow-red sequence absent')
        if entry is None:issues.append('ego intersection entry not measured')
        if case['variable_assignments']['obey_red']['value'] and entry_state and 'Red' in entry_state:
            issues.append('obey-red case entered on red; repair controller at same setting')
    else:
        entry=first_entry_bracket(samples,'ego',-7)
        line=-11
        stopped=[]
        for s in samples:
            if max(v[0] for v in s['ego']['body_vertices_m'])<line and s['ego']['speed_mps']<.05:
                stopped.append(s)
        other_stopped=any(s['other'] and s['other']['speed_mps']<.05 for s in samples)
        other_inside=any(s['other'] and -7<=s['other']['position_m'][1]<=7 for s in samples)
        all_off=bool(samples) and all(len(s['signal_devices'])>=4 and
            all('Off' in d['state'] for d in s['signal_devices']) for s in samples)
        measurements.update({'body_front_entry_bracket_s':entry,'preline_stationary_samples':len(stopped),
            'earlier_vehicle_stopped':other_stopped,'other_intersection_occupancy':other_inside,
            'all_four_native_signals_off':all_off,'occluders':setup['occluders'],
            'requested_halt':case['variable_assignments']['commanded_halt']['value']})
        if not all_off:issues.append('native four-head signal inoperability absent')
        if not setup['occluders']:issues.append('physical occluders absent')
        if entry is None:issues.append('ego entry not measured')
        if case['variable_assignments']['commanded_halt']['value'] and len(stopped)<20:
            issues.append('requested preline complete stop not observed for 1 s')
        if not (other_stopped and other_inside):issues.append('earlier-stopped or inside counterpart not observed')
    follow=json.loads(json.dumps(cfg))
    adjustment=[]
    if kind=='following' and measurements.get('measured_gap_mean_m') is not None:
        delta=measurements['measured_gap_mean_m']-measurements['requested_gap_m']
        if delta>2:
            follow['controller']['gap_kp']=min(1.0,follow['controller']['gap_kp']+0.1)
            adjustment.append('increase gap correction gain for excessive measured separation')
        elif delta<-2:
            follow['controller']['gap_kp']=max(0.1,follow['controller']['gap_kp']-0.1)
            adjustment.append('decrease gap correction gain for too-small measured separation')
    if kind in ('absolute_speed','posted_speed') and measurements.get('measured_window_mean_mps') is not None:
        if measurements['measured_window_mean_mps']<measurements['requested_speed_mps']-1:
            follow['controller']['speed_kp']=min(0.5,follow['controller']['speed_kp']+0.07)
            adjustment.append('increase speed tracking gain; remeasure actual vehicle limit')
    if kind=='yellow_red' and case['variable_assignments']['obey_red']['value'] and \
            measurements.get('entry_signal_state') and 'Red' in measurements['entry_signal_state']:
        follow['controller']['red_brake_start_x_m']-=10
        adjustment.append('begin red braking 10 m earlier at the same signal sequence')
    if kind=='inoperative_signal' and case['variable_assignments']['commanded_halt']['value'] and \
            measurements.get('preline_stationary_samples',0)<20:
        follow['controller']['stop_brake_start_x_m']-=10
        adjustment.append('begin preline stop braking 10 m earlier')
    follow['capability_follow_up']={'same_case_id':case['case_id'],
        'preserve_case_targets':True,'engineering_adjustments':adjustment,
        'requires_new_recorded_attempt':bool(issues)}
    return {'format':'partition04-capability-report-v1','case_id':case['case_id'],
        'measurements':measurements,'issues':issues,
        'decision':'repair_same_frozen_case' if issues else 'inspect_original_native_evidence',
        'follow_up_configuration':follow,
        'physical_acceptance':False,'legal_verdict':None,
        'unresolved':['actual camera legibility','public-way/device authority synthetic context',
                      'native motion and visibility beyond CPU proof','final encoded delivery video validation']}


def native_result(attempt,report):
    from worker_exchange.native_output import write_result
    attempt=pathlib.Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text());case=cfg['case']
    samples=rows(attempt/'physical_samples.jsonl')
    target=case['variable_assignments']['commanded_approach_speed']['value']
    measured=report['measurements'].get('measured_window_mean_mps')
    if measured is None:
        measured=report['measurements'].get('governed_full_trace_max_mps')
    if measured is None:
        measured=max(s['ego']['speed_mps'] for s in samples)
    completed_episode=(len(samples)==cfg['max_ticks'] and
        samples[-1]['time_s']-samples[0]['time_s']>=cfg['duration_s']-0.11 and
        samples[-1]['ego_route_index']>samples[0]['ego_route_index'] and
        samples[-1]['ego']['position_m'][0]>samples[0]['ego']['position_m'][0])
    return {'case_id':case['case_id'],'measured_values':report['measurements'],
        'target_checks':[{'target':'case_controller_target','requested':target,'measured':measured,
            'method':'saved original physical_samples.jsonl; full-trace maximum when requested window absent',
            'tolerance':1.0,'matched':measured is not None and isinstance(target,(int,float)) and abs(measured-target)<=1.0,
            'physical_cause_confirmed':False,'cause_evidence':'physical_samples.jsonl; diagnostic subset cannot establish cause'}],
        'setup_confirmed':False,'behavior_attempted':bool(samples),
        'maneuver_completed':completed_episode,
        'termination_reason':'diagnostic subset or unverified physical motion',
        'physical_failure_flags':{'detection_validated':False},
        'trace_reference':'trace.jsonl','video_references':['view%d.mkv'%i for i in range(4)],
        'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],
        'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'}
            for c in case['recording_description']['channels']]+[
            {'name':c['name'],'unit':c['unit'],'reference':'context.json'}
            for c in case['recording_description']['context_inputs']],
        'realized_observables':{},'physical_acceptance':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    report=assess(a.attempt)
    pathlib.Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
    from worker_exchange.native_output import write_result
    write_result(a.attempt,native_result(a.attempt,report))
