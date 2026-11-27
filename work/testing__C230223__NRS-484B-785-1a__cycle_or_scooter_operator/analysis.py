"""Saved-only source-bound scooter, designated-lane, speed and ordinance measurements."""
import argparse
import hashlib
import json
from pathlib import Path
from package_spec import AID, CAMERA_NAMES
from scooter_785 import CASES, SOURCE_ROLES, measure_original, need, qualifying_device, validate_scene, inside


def source(folder, name):
    path = folder / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: '+name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sealed_scooter_measurement(value):
    return value


def diagnostic_measure(rows, scene, case):
    need(len(rows) >= 3, 'diagnostic scooter frames missing')
    speeds = [row['speed_mps']/.44704 for row in rows]
    occupancy = [any(inside(point, scene['bicycle_lane_rect_m']) for point in row['body_corners_xy']) for row in rows]
    return {'case_id': AID+'__'+case.name,
            'requested_speed_mph': case.speed_mph,
            'steady_mean_speed_mph': sum(speeds)/len(speeds),
            'steady_max_speed_mph': max(speeds),
            'all_frame_max_speed_mph': max(speeds),
            'bicycle_lane_occupied_frames': sum(occupancy),
            'bicycle_lane_occupancy_requested': case.in_lane,
            'qualifying_device_from_source': qualifying_device(scene['device']),
            'ordinance_context_from_source': scene['ordinance_context'],
            'ordinance_effect_judgment': None, 'legal_verdict': None}


def analyze(attempt):
    folder = Path(attempt).resolve()
    config = json.loads(source(folder, 'config.json').read_text())
    case_id = config['selected_case_id']
    case = next((item for item in CASES if case_id == AID+'__'+item.name), None)
    need(case is not None, 'unknown exact scooter case')
    receipt = json.loads(source(folder, 'original-source-receipt.json').read_text())
    diagnostic = receipt.get('diagnostic_fixture') is True
    need(receipt.get('source_kind') == ('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture') and
         receipt.get('case_id') == case_id, 'scooter source provenance differs')
    for key, name in (('history_sha256','scooter-history.json'),
                      ('trace_sha256','trace.jsonl'),
                      ('frame_map_sha256','video_frames.jsonl')):
        need(receipt.get(key) == sha(source(folder,name)), 'sealed original scooter source differs: '+name)
    history = json.loads(source(folder,'scooter-history.json').read_text())
    rows, scene = history['samples'], history['scene']
    validate_scene(scene,case)
    trace = [json.loads(row) for row in source(folder,'trace.jsonl').read_text().splitlines()]
    frame_map = [json.loads(row) for row in source(folder,'video_frames.jsonl').read_text().splitlines()]
    need(history.get('assignment_id') == AID and history.get('case_id') == case_id and
         len(rows) == len(trace) == len(frame_map) and len(rows)>=3,
         'scooter case or original frame count differs')
    for index,(row,t,mapping) in enumerate(zip(rows,trace,frame_map)):
        need(row['frame'] == mapping['video_frame'] == index and
             row['original_frame'] == row['native_frame'] == t['frame'] == mapping['carla_frame'] == mapping['native_frame'] and
             row['time_s'] == t['time_s'] == mapping['time_s'] and
             row['speed_mps'] == t['speed_mps'] and row['native_actor_id'] == history['native_actor_id'],
             'original scooter trace/frame/body join differs')
        for role in SOURCE_ROLES:
            need(row[role+'_source_sha256'] == scene[role+'_source_sha256'],
                 'original source changed: '+role)
        if not diagnostic:
            need(row['position_xyz_m'] == t['position_m'], 'original scooter pose differs')
    measured = diagnostic_measure(rows,scene,case) if diagnostic else None
    if not diagnostic:
        try:
            measured = measure_original(rows,scene,case)
        except ValueError as error:
            measured = {'measured':False,'physical_gap':str(error),
                        'ordinance_effect_judgment':None,'legal_verdict':None}
    values = {
        'scooter_qualification': {'qualifies':qualifying_device(scene['device']),
                                  'device':scene['device'],
                                  'source_sha256':scene['device_specification_source_sha256']},
        'bicycle_lane_occupancy': {'designated_lane_id':scene['lane_designation_id'],
                                   'occupied_frames':measured.get('bicycle_lane_occupied_frames',0),
                                   'measured':measured.get('measured',True)},
        'speed_history_mph': {'requested_mph':case.speed_mph,
                              'steady_mean_mph':measured.get('steady_mean_speed_mph'),
                              'steady_max_mph':measured.get('steady_max_speed_mph'),
                              'all_frame_max_mph':measured.get('all_frame_max_speed_mph'),
                              'source_frame_count':len(rows),
                              'statutory_limit_mph':15},
        'ordinance_context': {'kind':scene['ordinance_context'],
                              'enacted_under_nrs_484a_469':scene['ordinance_enacted_under_nrs_484a_469'],
                              'official_text_sha256':scene.get('ordinance_text_sha256'),
                              'effect_judgment':None}}
    source_names=('scooter-history.json','original-source-receipt.json','trace.jsonl','video_frames.jsonl')
    source_hashes={name:sha(source(folder,name)) for name in source_names}
    measurements={key:{'method':'source_sealed_scooter_measurement','value':source_sealed_scooter_measurement(value),
                       'sources':source_hashes} for key,value in values.items()}
    recorded=config['case']['recording_description']
    evidence=[]
    for channel in recorded['channels']:
        name=channel['name']
        path=folder/('channel-'+name+'.jsonl')
        content=''.join(json.dumps({'time_s':row['time_s'],
              'value': row['speed_mps']/.44704 if name=='ego_speed_mph' else
                       any(inside(p,scene['bicycle_lane_rect_m']) for p in row['body_corners_xy']) if name=='ego_body_lane_occupancy' else
                       {'original_frame':row['original_frame'],'native_actor_id':row['native_actor_id']} if name=='original_frame_join' else
                       scene['device'] if name=='scooter_device_identity' else
                       scene['lane_designation_id'] if name=='bicycle_lane_designation' else
                       scene['ordinance_context']},sort_keys=True)+'\n' for row in rows)
        if path.exists():
            need(path.read_text()==content,'derived scooter channel differs: '+name)
        else:
            path.write_text(content)
        evidence.append({'name':name,'unit':channel['unit'],'reference':path.name})
    context=folder/'channel-reviewed_scooter_site.json'
    content=json.dumps({'site_sha256':history['reviewed_site_sha256'],
                        'source_hashes':{role:scene[role+'_source_sha256'] for role in SOURCE_ROLES}},sort_keys=True)+'\n'
    if context.exists():
        need(context.read_text()==content,'reviewed scooter site context differs')
    else:
        context.write_text(content)
    evidence.append({'name':'reviewed_scooter_site','unit':'source record','reference':context.name})
    from worker_exchange.native_output import physical_result,write_result
    result={'case_id':case_id,'measured_values':values,
            'target_checks':[{'target':'original scooter lane and speed source capture',
                              'requested':case.speed_mph,'measured':measured.get('steady_mean_speed_mph'),
                              'method':'source-sealed Native velocity and body frames',
                              'tolerance':.25,'matched':measured.get('steady_mean_speed_mph') is not None and abs(measured['steady_mean_speed_mph']-case.speed_mph)<=.25,
                              'physical_cause_confirmed':False,'cause_evidence':source_hashes}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'saved physical and legal review pending',
            'physical_failure_flags':['physical_acceptance_unverified'],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in CAMERA_NAMES],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':recorded,'recording_evidence':evidence,
            'realized_observables':{},'diagnostic_fixture':diagnostic,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    result=physical_result(folder,result)
    write_result(folder,result)
    return {'format':'worker-analysis-report','case_id':case_id,'analysis_complete':True,
            'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,
            'legal_verdict_claimed':False,'measurements':measurements,
            'physical_checks':result['physical_checks'],
            'realized_observables':result['realized_observables'],
            'limitations':['Physical 15 mph boundary and ordinance effect require original source review.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior scooter analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt),indent=2)+'\n')
