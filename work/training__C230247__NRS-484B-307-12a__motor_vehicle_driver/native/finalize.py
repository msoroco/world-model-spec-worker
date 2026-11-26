"""Saved-only source-bound analysis for the two exact overhead-arrow cases."""
import argparse
import hashlib
import json
from pathlib import Path

from lane_arrow_meter import measure
from signal_source import map_inventory

CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root,name):
    path=root/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def overhead_lane_mapping(signal_rows,inventory):
    return {'signal_id':inventory['id'],'lane_id':inventory['lane_id'],
            'mount_m':inventory['mount_m'],
            'all_frames_bound_to_map':all(r['signal']['id']==inventory['id'] and
                r['signal']['lane_id']==inventory['lane_id'] and
                r['signal']['mount_m']==inventory['mount_m'] for r in signal_rows)}


def facing_downward_arrow(measured):
    return measured['facing_green_proposed_frames']


def proposed_lane_witness(measured,target_lane):
    return {'target_lane_id':target_lane,
            'facing_green_proposed_frames':measured['facing_green_proposed_frames'],
            'facing_green_occupied_frames':measured['facing_green_occupied_frames'],
            'signal_lane_id':measured['observations'][0]['signal_lane_id']}


def finalize(attempt,output):
    root=Path(attempt)
    cfg=json.loads(required(root,'config.json').read_text())
    signal_rows=rows(required(root,'native-signal-rows.jsonl'))
    inventory=map_inventory(required(root,'native-map-readback.xodr').read_text())
    frame_rows=rows(required(root,'video_frames.jsonl'))
    trace_rows=rows(required(root,'trace.jsonl'))
    evidence_rows=rows(required(root,'capture/evidence.jsonl'))
    for camera in CAMERAS:
        required(root,camera+'.mkv')
    if any(len(seq)!=600 for seq in (signal_rows,frame_rows,trace_rows,evidence_rows)):
        raise ValueError('Full 600-frame original source required')
    for index,(signal,frame,trace,event) in enumerate(zip(signal_rows,frame_rows,trace_rows,evidence_rows)):
        native=signal.get('native_frame')
        if (signal.get('frame')!=index or frame.get('native_frame')!=native or
            frame.get('carla_frame')!=native or trace.get('frame')!=native or
            event.get('original_frame')!=native or
            any(frame.get('camera_native_frames',{}).get(name)!=native for name in CAMERAS)):
            raise ValueError('Original signal, trace and camera frame join differs')
    measured=measure({'frames':signal_rows})
    mapping=overhead_lane_mapping(signal_rows,inventory)
    if not mapping['all_frames_bound_to_map']:
        raise ValueError('Original signal source differs from map inventory')
    target_lane=cfg['case']['target_lane_id']
    if target_lane not in (-1,-2):
        raise ValueError('Exact target lane missing')
    if any(r['proposed_lane_id']!=target_lane or r['occupied_lane_id']!=target_lane for r in measured['observations']):
        raise ValueError('Original actor did not remain in the exact proposed lane')
    first=trace_rows[0]['position_m']
    last=trace_rows[-1]['position_m']
    progress=last[0]-first[0]
    if not isinstance(progress,(int,float)):
        raise ValueError('Original travel progress absent')
    arrow_frames=measured['facing_green_proposed_frames']
    diagnostic=signal_rows[0].get('diagnostic_fixture',False)
    channels=root/'channels'
    channels.mkdir(exist_ok=True)
    channel_refs=[]
    for channel in cfg['recording_description']['channels']:
        name=channel['name']
        path=channels/(name.replace('/','_')+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':row['time_s'],
            'value':row['vehicle']['lane_id'] if name=='rel.occupies' else {
            'indication':row['signal']['indication'],
            'signal_lane_id':row['signal']['lane_id'],
            'occupied_lane_id':row['vehicle']['lane_id'],
            'proposed_lane_id':row['vehicle']['proposed_lane_id']}},
            separators=(',',':'))+'\n' for row in signal_rows))
        channel_refs.append({'name':name,'unit':channel['unit'],
                             'reference':'channels/'+path.name})
    result={'case_id':cfg['case_id'],
        'measured_values':{'facing_green_proposed_frames':arrow_frames,
                           'original_travel_progress_m':progress},
        'target_checks':[{'target':'facing_green_arrow_over_proposed_lane',
            'requested':target_lane==-1,'measured':arrow_frames==600,
            'method':'original per-frame Native actor, signal and map-inventory join',
            'tolerance':0,'matched':(arrow_frames==600)==(target_lane==-1),
            'physical_cause_confirmed':False,
            'cause_evidence':['native-signal-rows.jsonl','video_frames.jsonl']},
            {'target':'authored_travel_progress_m','requested':75.0,
            'measured':progress,'method':'original trace endpoints',
            'tolerance':1.0,'matched':abs(progress-75.0)<=1.0,
            'physical_cause_confirmed':False,'cause_evidence':['trace.jsonl']}],
        'setup_confirmed':not diagnostic,'behavior_attempted':not diagnostic,
        'maneuver_completed':not diagnostic and progress>=40.0,
        'termination_reason':'full original 600-frame window' if not diagnostic else 'synthetic CPU diagnostic',
        'physical_failure_flags':['green_arrow_pixels_and_official_authority_pending_review'],
        'trace_reference':'trace.jsonl',
        'video_references':[name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':cfg['recording_description'],
        'recording_evidence':channel_refs,
        'realized_observables':{
            'rel.occupies':{'value':signal_rows[0]['vehicle']['lane_id'],
                'unit':'lane_id','method':'original actor body and waypoint projection',
                'time_window':'600 original frames','statistic':'first',
                'reference':'channels/rel.occupies.jsonl',
                'sample_window_s':[signal_rows[0]['time_s'],signal_rows[-1]['time_s']]},
            'facing_green_proposed_frames':{'value':arrow_frames,'unit':'frames',
                'method':'original Native signal and actor frame join','time_window':'600 frames',
                'statistic':'count','reference':'native-signal-rows.jsonl'},
            'original_travel_progress_m':{'value':progress,'unit':'m',
                'method':'trace endpoint displacement','time_window':'600 frames',
                'statistic':'endpoint_difference','reference':'trace.jsonl'}},
        'provenance_kind':'synthetic_cpu' if diagnostic else 'native',
        'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import write_result
    write_result(root,result)
    report={'format':'c230247-lane-arrow-saved-analysis-v1',
        'case_id':cfg['case_id'],'source_sha256':{
            name:sha(root/name) for name in ('native-signal-rows.jsonl',
            'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl')},
        'measurements':{
            'overhead_lane_mapping':{'value':mapping,'method':'overhead_lane_mapping',
                'sources':{name:sha(root/name) for name in ('native-signal-rows.jsonl','native-map-readback.xodr')}},
            'facing_downward_arrow_frames':{'value':facing_downward_arrow(measured),
                'method':'facing_downward_arrow',
                'sources':{name:sha(root/name) for name in ('native-signal-rows.jsonl','video_frames.jsonl')}},
            'proposed_lane_witness':{'value':proposed_lane_witness(measured,target_lane),
                'method':'proposed_lane_witness',
                'sources':{name:sha(root/name) for name in ('native-signal-rows.jsonl','trace.jsonl','capture/evidence.jsonl')}},
            'meter':measured},'original_native_source':not diagnostic,
        'official_authority_review_pending':True,'actual_pixels_review_pending':True,
        'legal_verdict':None}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':
    main()
