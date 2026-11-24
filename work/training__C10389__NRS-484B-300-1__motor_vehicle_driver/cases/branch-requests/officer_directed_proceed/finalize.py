"""Saved-only diagnostic finalizer for four statutory branch request pairs."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root,name):
    path=Path(root)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def rows(root,name):return [json.loads(x) for x in required(root,name).read_text().splitlines() if x]


def measure_branch_response(root):
    root=Path(root);config=json.loads(required(root,'config.json').read_text())
    actors=rows(root,'native-raw-actors.jsonl');mapping=json.loads(required(root,'native-map-readback.json').read_text())
    if len(actors)!=600 or mapping.get('source_kind')!='synthetic_cpu':
        raise ValueError('Diagnostic source or 600-frame actor window changed')
    suffix=config['case_id'].rsplit('__',1)[1];kind='signal' if suffix.startswith('signal_') else 'officer'
    expected=('3892','1000001') if kind=='signal' else ('3891','206')
    landmark=mapping['stop_landmark_readback']
    if (landmark.get('id'),landmark.get('type'))!=expected or landmark.get('s_m')!=50.0:
        raise ValueError('Branch diagnostic device source changed')
    stopped=0;crossings=0;signal_states=set();officer_frames=0
    for index,row in enumerate(actors):
        if row.get('frame')!=index or row.get('source_kind')!='synthetic_cpu':
            raise ValueError('Diagnostic actor/frame source changed')
        ego=row['ego'];body=ego['body_native_xyz_m']
        if len(body)!=8:raise ValueError('Diagnostic actor body source changed')
        front=max(point[0] for point in body)
        if front<50 and ego['speed_mps']<0.1:stopped+=1
        if front>=50:crossings+=1
        if kind=='signal':
            if row.get('signal_state_observed') is None:raise ValueError('Signal state diagnostic source missing')
            signal_states.add(row['signal_state_observed'])
        elif row.get('officer_actor') is not None:officer_frames+=1
    return {'value':{'stopped_before_frames':stopped,'body_at_station_frames':crossings,
                     'signal_states':sorted(signal_states),'officer_actor_frames':officer_frames},
            'method':'measure_branch_response',
            'sources':{'native-raw-actors.jsonl':sha(root/'native-raw-actors.jsonl'),
                       'native-map-readback.json':sha(root/'native-map-readback.json')},
            'scope':'Synthetic CPU branch diagnostic; authority and legal effect unverified'}


def channel_value(name,actor,frame,mapping):
    ego=actor['ego'];landmark=mapping['stop_landmark_readback']
    if name=='dev.traffic_signal':return actor.get('signal_state_observed') or {'status':'not_observed_in_synthetic_fixture'}
    if name=='dev.regulatory_sign':return landmark['type'] if landmark['type']=='206' else {'status':'not_observed_in_synthetic_fixture'}
    if name=='dev.stop_sign':return landmark['id'] if landmark['type']=='206' else {'status':'not_observed_in_synthetic_fixture'}
    if name in ('dev.yield_sign','dev.speed_limit_sign','dev.lane_control_signal'):return {'status':'not_observed_in_synthetic_fixture'}
    if name=='dev.governs':return {'ego_road_id':actor['observed_road_id'],'ego_lane_id':actor['observed_lane_id'],'device_road_id':landmark['road_id'],'legally_verified':False}
    if name=='dev.position':return {'station_s_m':landmark['s_m'],'ego_center_native_xyz_m':ego['center_native_xyz_m']}
    if name=='kin.velocity':return ego['velocity_native_xyz_mps']
    if name=='rel.occupies':return ego['body_native_xyz_m']
    if name=='dev.human_direction':return {'officer_actor':actor.get('officer_actor'),'police_authority_verified':False,'direction_verified':False}
    if name=='camera_frame_join':return {'native_frame':frame['native_frame'],'video_frame':frame['video_frame']}
    raise ValueError('Unknown diagnostic recording channel: '+name)


def finalize(attempt,output):
    root=Path(attempt);config=json.loads(required(root,'config.json').read_text())
    measurement=measure_branch_response(root)
    actors=rows(root,'native-raw-actors.jsonl');frames=rows(root,'video_frames.jsonl')
    trace=rows(root,'trace.jsonl');evidence=rows(root,'capture/evidence.jsonl')
    if any(len(source)!=600 for source in (actors,frames,trace,evidence)):
        raise ValueError('Retained 600-frame branch source counts differ')
    for actor,frame,motion,source in zip(actors,frames,trace,evidence):
        native=actor['native_frame']
        if any(value!=native for value in (frame['native_frame'],frame['carla_frame'],motion['frame'],source['original_frame'])):
            raise ValueError('Native branch frame join differs')
        if any(abs(value-actor['time_s'])>1e-6 for value in (frame['time_s'],motion['time_s'],source['recording_time_s'])):
            raise ValueError('Native branch time join differs')
    channels=root/'channels'
    if channels.exists():raise ValueError('Fixture supplied derived channels')
    channels.mkdir();recorded=config['recording_description']
    mapping=json.loads((root/'native-map-readback.json').read_text())
    for channel in recorded['channels']:
        name=channel['name'];path=channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':a['time_s'],'value':channel_value(name,a,f,mapping)},allow_nan=False)+'\n' for a,f in zip(actors,frames)))
    context={'official_placement_authority':{'status':'unverified_synthetic_fixture','authority_source':None}}
    (channels/'official_placement_authority.json').write_text(json.dumps(context)+'\n')
    values=measurement['value'];suffix=config['case_id'].rsplit('__',1)[1]
    requested_stop=suffix in ('signal_red_stop','officer_no_direction_stop')
    matched=(values['stopped_before_frames']>=20 if requested_stop else values['body_at_station_frames']>0)
    result={'case_id':config['case_id'],'measured_values':values,
            'target_checks':[{'target':'authored statutory branch motion request',
                'requested':'stop before station' if requested_stop else 'pass station',
                'measured':values,'method':'600 retained synthetic body/source rows',
                'tolerance':'20 diagnostic frames, not a legal threshold',
                'matched':matched,'physical_cause_confirmed':False,
                'cause_evidence':['native-raw-actors.jsonl','native-map-readback.json']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'synthetic full-duration source fixture processed',
            'physical_failure_flags':['original_native_unobserved','official_placement_unverified',
                                      'police_authority_unverified','source_pixels_unreviewed'],
            'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':recorded,
            'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in recorded['channels']]+[{'name':'official_placement_authority','unit':'source_document','reference':'channels/official_placement_authority.json'}],
            'realized_observables':{},'provenance_kind':'synthetic_cpu_fixture',
            'accepted':False,'legal_verdict_claimed':False}
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    report={'format':'c10389-branch-diagnostic-analysis-v1','case_id':config['case_id'],
            'measurements':{'branch_response':measurement},'source_only':True,
            'official_placement_verified':False,'police_authority_verified':False,
            'legal_outcome_claimed':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();print(json.dumps(finalize(a.attempt,a.output)))
