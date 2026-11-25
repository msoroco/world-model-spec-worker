"""Recorded-only C227853 departure analysis; never a legal safety verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from departure_saved_measure import measure_original

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
SOURCES = ('departure-trace.jsonl', 'video_frames.jsonl',
           'departure-context.json', 'road.xodr')


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def departure_observation(source):
    return measure_original(*(source[name].read_bytes() for name in SOURCES))


def analysis_report(folder, contract=None):
    config = json.loads(required(folder, 'config.json').read_text())
    source = {name: required(folder, name) for name in SOURCES}
    measured = departure_observation(source)
    context=json.loads(source['departure-context.json'].read_text())
    if (context.get('initial_status') != config.get('requested_initial_status',
                                                   'parked_no_loading') or
            context.get('parking_permitted') != config.get('requested_parking_permitted', True)):
        raise ValueError('Source context differs from requested statutory branch')
    if context.get('source_kind')=='native_saved_sample':
        manifest=required(folder,'authority/manifest.json')
        if sha(manifest)!=context.get('authority_manifest_sha256'):
            raise ValueError('Retained authority manifest hash differs')
        for fact in ('highway_dedication','public_access','curb_permission','parking_purpose'):
            retained=required(folder,'authority/'+fact+'.source')
            if sha(retained)!=context.get(fact+'_source_sha256'):
                raise ValueError('Retained authority source hash differs: '+fact)
    return {'format':'c227853-departure-analysis-v1','case_id':config['case_id'],
            'analysis_complete':True,'legal_verdict_claimed':False,
            'measurements':{'departure_observation':{
                'method':'departure_observation','value':measured,
                'sources':{name:sha(path) for name,path in source.items()}}},
            'limitations':['Movement made with safety remains a legal judgment.',
                           'Diagnostic fixtures do not establish highway authority, '
                           'parking permission, physical trajectories or actual pixels.']}


def decoded_frames(path):
    result = subprocess.run(['ffprobe','-v','error','-count_frames',
        '-select_streams','v:0','-show_entries','stream=nb_read_frames',
        '-of','default=noprint_wrappers=1:nokey=1',str(path)],
        capture_output=True,text=True,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + path.name)
    return int(result.stdout.strip())


def verify_capture_joins(attempt):
    names = ('trace.jsonl','capture/evidence.jsonl',
             'capture/native/frames.jsonl','video_frames.jsonl',
             'departure-trace.jsonl')
    rows = [[json.loads(line) for line in required(attempt,name).read_text().splitlines()]
            for name in names]
    if any(len(part)!=600 for part in rows):
        raise ValueError('Original Core, evidence and departure frame count differs')
    previous = -1
    for index,(core,evidence,graph,mapping,departure) in enumerate(zip(*rows)):
        frame = mapping.get('native_frame')
        if type(frame) is not int or frame<=previous:
            raise ValueError('Original Core frame order differs')
        previous=frame
        if (core.get('frame')!=frame or evidence.get('original_frame')!=frame or
                graph.get('frame')!=frame or departure.get('native_frame')!=frame or
                mapping.get('video_frame')!=index):
            raise ValueError('Original Core/evidence/graph/departure frame join differs')
        if (abs(core['time_s']-mapping['time_s'])>.005 or
                abs(evidence['recording_time_s']-mapping['time_s'])>.005 or
                abs(departure['time_s']-mapping['time_s'])>.005):
            raise ValueError('Original Core/evidence/departure time join differs')
    return {'frame_count':600,'source_sha256':{name:sha(required(attempt,name))
                                              for name in names}}


def derive_channels(attempt):
    attempt=Path(attempt)
    rows=[json.loads(line) for line in required(attempt,'departure-trace.jsonl').read_text().splitlines()]
    folder=attempt/'channels'
    folder.mkdir(exist_ok=True)
    targets={'participant_footprints':[], 'participant_velocity':[]}
    for row in rows:
        time=row['time_s']
        targets['participant_footprints'].append({'time_s':time,
            'value':{'ego_id':row['ego_id'],'traffic_id':row['traffic_id'],
                     'ego_footprint_xy_m':row['ego_footprint_xy_m'],
                     'traffic_footprint_xy_m':row['traffic_footprint_xy_m']}})
        targets['participant_velocity'].append({'time_s':time,
            'value':{'ego_speed_mps':row['ego_speed_mps'],
                     'traffic_speed_mps':row['traffic_speed_mps']}})
    for name,items in targets.items():
        path=folder/(name+'.jsonl')
        if path.exists():
            raise ValueError('Derived channel already exists: '+name)
        path.write_text('\n'.join(json.dumps(item,allow_nan=False) for item in items)+'\n')
    return {name:'channels/'+name+'.jsonl' for name in targets}


def finalize(attempt,output):
    from worker_exchange.native_output import provenance_record,write_result
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    config=json.loads(required(attempt,'config.json').read_text())
    if config.get('rate_hz')!=20 or config.get('duration_s')!=30:
        raise ValueError('C227853 original recording contract changed')
    report=analysis_report(attempt)
    measured=report['measurements']['departure_observation']['value']
    joins=verify_capture_joins(attempt)
    channels=derive_channels(attempt)
    counts={name:decoded_frames(required(attempt,name)) for name in VIDEOS}
    if set(counts.values())!={600}:
        raise ValueError('Original four-camera frame count differs')
    provenance=provenance_record(attempt)
    native=provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    for item in config['recording_description']['channels']:
        if item['name'] not in channels:
            raise ValueError('Unknown required Native channel: '+item['name'])
    result={'case_id':config['case_id'],'measured_values':measured,
        'target_checks':[{'target':'sourced highway stopped, standing or parked departure with surrounding traffic',
            'requested':'closer traffic' if config['approaching_conflict_requested'] else 'clear traffic',
            'measured':{'surface_gap_at_start_m':measured['surface_gap_at_start_m'],
                        'minimum_surface_gap_during_first_10s_after_start_m':
                            measured['minimum_surface_gap_during_first_10s_after_start_m'],
                        'max_observed_traffic_deceleration_mps2':
                            measured['max_observed_traffic_deceleration_mps2']},
            'method':'original same-tick participant bodies and velocities',
            'tolerance':'continuous source values; no legal cutoff',
            'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':list(SOURCES)}],
        'setup_confirmed':native,
        'behavior_attempted':native,'maneuver_completed':False,
        'termination_reason':'600 original Native frames retained',
        'physical_failure_flags':['highway_and_permission_require_independent_review',
                                  'departure_safety_and_actual_pixels_require_physical_review'],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':[{'name':name,'unit':item['unit'],'reference':channels[name]}
                              for item in config['recording_description']['channels']
                              for name in [item['name']]],
        'realized_observables':{'departure_surface_gap_m':{
            'value':measured['surface_gap_at_start_m'],'unit':'m',
            'method':'original participant footprint separation at movement onset',
            'time_window':'original start frame','statistic':'surface distance',
            'reference':'departure-trace.jsonl'}},
        'provenance_kind':provenance['provenance_kind'],
        'diagnostic_fixture':provenance['diagnostic_fixture'],
        'accepted':False,'legal_verdict_claimed':False}
    write_result(attempt,result)
    report.update(candidate_id=config['candidate_id'],original_joins=joins,
                  source_video_frames=counts,provenance=provenance)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    print(json.dumps(finalize(a.attempt,a.output)))
