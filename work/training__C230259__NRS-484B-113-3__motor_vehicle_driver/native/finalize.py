"""Recorded-only source measurement and Native result; legal precedence unresolved."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_motion import CAMERAS,measure,rows
from measure_pedestrian import measure_pedestrian


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inputs(attempt):
    names=('native-motion.jsonl','traffic-context.json','video_frames.jsonl')
    for name in names:
        if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
    return {name:sha(attempt/name) for name in names}


def measure_moving_requirement(attempt):
    attempt=Path(attempt);value=measure(attempt)
    return {'value':{'backing_frames':value['backing_frame_count'],
        'other_moving_frames':value['other_moving_frame_count'],
        'simultaneous_frames':value['simultaneous_backing_and_other_moving_frame_count'],
        'ego_conflict_entry_frame':value['ego_first_conflict_region_frame'],
        'other_conflict_entry_frame':value['other_first_conflict_region_frame'],
        'minimum_center_gap_m':value['minimum_center_gap_during_simultaneous_motion_m']},
        'method':'measure_moving_requirement','sources':_inputs(attempt)}


def measure_pedestrian_requirement(attempt):
    attempt=Path(attempt);value=measure_pedestrian(attempt)
    return {'value':{'backing_frames':value['backing_frame_count'],
        'pedestrian_moving_frames':value['pedestrian_moving_frame_count'],
        'simultaneous_frames':value['simultaneous_backing_and_pedestrian_motion_frame_count'],
        'ego_conflict_entry_frame':value['ego_first_conflict_region_frame'],
        'pedestrian_conflict_entry_frame':value['pedestrian_first_conflict_region_frame'],
        'minimum_center_gap_m':value['minimum_center_gap_during_backing_and_pedestrian_motion_m']},
        'method':'measure_pedestrian_requirement','sources':_inputs(attempt)}


def _video_frames(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    run=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
        capture_output=True,text=True,timeout=120)
    if run.returncode or not run.stdout.strip().isdigit():
        raise ValueError('Original source video decode failed: '+path.name)
    return int(run.stdout.strip())


def _channels(attempt,description):
    motion=rows(attempt/'native-motion.jsonl')
    context=json.loads((attempt/'traffic-context.json').read_text())
    destination=attempt/'channels';destination.mkdir(exist_ok=True)
    first=next((row['time_s'] for row in motion
        if row['ego']['velocity_xy_mps'][0]<-.1),None)
    if first is None:raise ValueError('No measured original backing onset')
    values={name:[] for name in (c['name'] for c in description['channels'])}
    for row in motion:
        time=row['time_s'];ego=row['ego'];other=row['other'];ped=row.get('pedestrian')
        backing=ego['velocity_xy_mps'][0]<-.1
        channel={'drv.backing':{'backing':backing,'ego':ego},
            'drv.yields_to':{'ego':ego,'other':other,'pedestrian':ped,'legal_verdict':'unresolved'},
            'ru.pedestrian':{'present':ped is not None,'actor':ped},
            'kin.velocity':{'ego':ego['velocity_xy_mps'],'other':other['velocity_xy_mps'],
                'pedestrian':ped['velocity_xy_mps'] if ped else None},
            'drv.arrival_order':{'ego':ego['center_xy_m'],'other':other['center_xy_m'],
                'pedestrian':ped['center_xy_m'] if ped else None,'conflict_region':context['conflict_region']},
            'drv.time_to_conflict':{'ego':ego,'other':other,'pedestrian':ped,
                'engineering_observation_only':True},
            'drv.hard_deceleration':{'other_velocity_xy_mps':other['velocity_xy_mps'],
                'cause_unresolved':True},
            'backing_onset_s':first,
            'native_body_pose_control':row,
            'camera_frame_join':{'native_frame':row['native_frame'],'video_frame':row['video_frame']}}
        for name in values:
            values[name].append(json.dumps({'time_s':time,'value':channel[name]},allow_nan=False))
    for name,lines in values.items():
        (destination/(name+'.jsonl')).write_text('\n'.join(lines)+'\n')


def finalize(attempt,output):
    from worker_exchange.native_output import write_result,physical_result
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use fresh saved finalization output')
    config=json.loads((attempt/'config.json').read_text())
    suffix=config['case_suffix'];pedestrian=suffix.startswith('pedestrian_')
    measured=measure_pedestrian_requirement(attempt) if pedestrian else measure_moving_requirement(attempt)
    count=config['duration_s']*config['rate_hz']
    video_counts={name:_video_frames(attempt/(name+'.mkv')) for name in CAMERAS}
    if any(n!=count for n in video_counts.values()):raise ValueError('Original camera frame count differs')
    if not (attempt/'trace.jsonl').is_file() or len((attempt/'trace.jsonl').read_text().splitlines())!=count:
        raise ValueError('Missing full original Native trace')
    _channels(attempt,config['recording_description'])
    evidence=[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'}
        for c in config['recording_description']['channels']]
    evidence.append({'name':'road_and_actor_context','unit':'structured','reference':'traffic-context.json'})
    values=measured['value']
    check={'target':'sampled backing and '+('pedestrian' if pedestrian else 'moving vehicle')+' motion',
        'requested':'observed source interaction','measured':values,'method':measured['method'],
        'tolerance':'50 ms sampled timing; no legal threshold',
        'matched':values['backing_frames']>0 and values['simultaneous_frames']>0,
        'physical_cause_confirmed':False,'cause_evidence':list(measured['sources'])}
    motion_rows=rows(attempt/'native-motion.jsonl')
    onset=next((row['time_s'] for row in motion_rows
        if row['ego']['velocity_xy_mps'][0]<-.1),None)
    if onset is None:raise ValueError('No measured original backing onset')
    onset_reference='channels/backing_onset_s.jsonl'
    realized={'backing_onset_s':{'unit':'s','method':'first original negative signed ego velocity',
        'time_window':'30 s original recording','statistic':'first','reference':onset_reference,
        'value':onset,'sample_window_s':[0.0,motion_rows[-1]['time_s']]}}
    result={'case_id':config['case_id'],'measured_values':values,'target_checks':[check],
        'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
        'termination_reason':'Full original duration retained; saved assessment pending',
        'physical_failure_flags':['original_pixels_and_precendence_review_pending'],
        'trace_reference':'trace.jsonl','video_references':[n+'.mkv' for n in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],'recording_evidence':evidence,
        'realized_observables':realized,'legal_verdict_claimed':False,'accepted':False}
    result=physical_result(attempt,result)
    result['realized_observables']['backing_onset_s']=realized['backing_onset_s']
    write_result(attempt,result)
    report={'format':'c230259-saved-measurement-v1','case_id':config['case_id'],
        'candidate_id':config['candidate_id'],
        'measurements':{'pedestrian_requirement' if pedestrian else 'moving_requirement':measured},
        'video_frames':video_counts,'physical_checks':result['physical_checks'],
        'scope':'Recorded source measurements and software checks only; no legal or physical acceptance'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()
