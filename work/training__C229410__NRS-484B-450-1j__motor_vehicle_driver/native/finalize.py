"""Recorded-only entrance observation; retain raw geometry and legal uncertainty."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from measure_entrance import measure

VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
JOINS=('trace.jsonl','capture/evidence.jsonl','capture/native/frames.jsonl',
       'video_frames.jsonl','native-vehicle.jsonl')


def required(folder,name):
    path=Path(folder)/name
    if not path.is_file():raise ValueError('Missing original source: '+name)
    return path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def verify_joins(attempt):
    streams=[rows(required(attempt,name)) for name in JOINS]
    if any(len(stream)!=600 for stream in streams):
        raise ValueError('Original Core, graph and parking stream count differs')
    previous=-1
    for index,(core,evidence,graph,mapping,parking) in enumerate(zip(*streams)):
        frame=mapping.get('native_frame')
        if type(frame) is not int or frame<=previous or mapping.get('video_frame')!=index:
            raise ValueError('Original parking frame order differs')
        previous=frame
        if (core.get('frame')!=frame or evidence.get('original_frame')!=frame or
                graph.get('frame')!=frame or parking.get('native_frame')!=frame or
                parking.get('video_frame')!=index):
            raise ValueError('Original parking/Core/evidence frame join differs')
        if any(abs(item.get('time_s',-1)-mapping['time_s'])>.005 for item in (core,graph,parking)):
            raise ValueError('Original parking time join differs')
        if abs(evidence.get('recording_time_s',-1)-mapping['time_s'])>.005:
            raise ValueError('Original parking evidence time join differs')
    return {name:sha(required(attempt,name)) for name in JOINS}


def decoded_frames(path):
    call=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
        str(path)],capture_output=True,text=True,timeout=120)
    if call.returncode or not call.stdout.strip().isdigit():
        raise ValueError('Original parking video decode failed: '+path.name)
    return int(call.stdout.strip())


def fire_station_entrance_observation(attempt):
    return measure(attempt)


def finalize(attempt,output):
    from worker_exchange.native_output import provenance_record,write_result
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior result; choose a fresh attempt')
    config=json.loads(required(attempt,'config.json').read_text())
    if config.get('rate_hz')!=20 or config.get('duration_s')!=30:
        raise ValueError('Parking capture contract differs')
    measured=fire_station_entrance_observation(attempt)
    context=json.loads(required(attempt,'entrance-context.json').read_text())
    if (context.get('initial_activity')!=config.get('initial_activity') or
            context.get('exception_context')!=config.get('exception_context')):
        raise ValueError('Original parking activity/exception source differs from selected case')
    joins=verify_joins(attempt)
    counts={name:decoded_frames(required(attempt,name)) for name in VIDEOS}
    if set(counts.values())!={600}:
        raise ValueError('Original parking video frame count differs')
    trace=rows(required(attempt,'native-vehicle.jsonl'))
    channel=attempt/'channels/parking_geometry.jsonl'
    channel.parent.mkdir(exist_ok=True)
    channel.write_text('\n'.join(json.dumps({'time_s':row['time_s'],
        'value':{'body_xy_m':row['body_xy_m'],'speed_mps':row['speed_mps']}})
        for row in trace)+'\n')
    provenance=provenance_record(attempt)
    native=provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    value=measured['stationary_min_body_edge_gap_m']
    result={'case_id':config['case_id'],'measured_values':measured,
        'target_checks':[{'target':'sourced stationary fire-station driveway side and extent',
            'requested':config.get('target'),'measured':{'raw_min_body_edge_gap_m':value,
            'road_sides_seen':measured['road_sides_seen']},
            'method':'original body corners, entrance geometry and same-tick frames',
            'tolerance':'raw distances only; statutory reference method and exceptions remain review',
            'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':['entrance-context.json','native-vehicle.jsonl','video_frames.jsonl']}],
        'setup_confirmed':native,'behavior_attempted':native,'maneuver_completed':False,
        'termination_reason':'600 original Native frames retained',
        'physical_failure_flags':['station_identity_and_entrance_require_independent_review',
            'statutory_reference_point_and_exception_review_pending'],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':[{'name':'parking_geometry','unit':'mixed',
            'reference':'channels/parking_geometry.jsonl'}],
        'realized_observables':{'raw_stationary_min_body_edge_gap_m':{'value':value,
            'unit':'m','method':'original vehicle body edge to sourced entrance interval',
            'time_window':'stationary original frames','statistic':'minimum',
            'reference':'native-vehicle.jsonl'}},
        'provenance_kind':provenance['provenance_kind'],
        'diagnostic_fixture':provenance['diagnostic_fixture'],
        'accepted':False,'legal_verdict_claimed':False}
    write_result(attempt,result)
    report={'format':'c229410-parking-analysis-v1','case_id':config['case_id'],
        'analysis_complete':True,'legal_verdict_claimed':False,
        'measurements':{'fire_station_entrance_observation':{'method':'fire_station_entrance_observation',
            'value':measured,'sources':{name:sha(required(attempt,name)) for name in
            ('entrance-context.json','native-vehicle.jsonl','video_frames.jsonl','road.xodr')}}},
        'original_joins':joins,'source_video_frames':counts,'provenance':provenance,
        'limitations':['Synthetic fixtures do not establish fire-station identity or actual pixels.',
            'The statute does not supply a body-edge reference point or convert this diagnostic into a legal verdict.']}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(finalize(a.attempt,a.output)))
