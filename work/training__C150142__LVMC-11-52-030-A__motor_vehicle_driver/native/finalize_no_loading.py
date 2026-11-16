"""Saved-only no-loading finalizer from retained bus and walker inventory rows."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_red_curb import measure, VIEWS
from measure_exceptions import measure as measure_exception
from exception_road import readback as read_road
from exception_duration import plan as duration_plan
from passenger_absence import derive as derive_passenger_absence


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, name):
    path = Path(attempt) / name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def rows(attempt, name):
    return [json.loads(line) for line in source(attempt, name).read_text().splitlines()
            if line.strip()]


def paint_context(map_readback):
    return {'paint_color': map_readback['paint_color'],
            'source_kind': map_readback['source_kind'],
            'start_x_m': map_readback['red_curb_start_x_m'],
            'end_x_m': map_readback['red_curb_end_x_m'],
            'curb_y_m': map_readback['curb_y_m']}


def red_occupancy(observation):
    return observation['red_curb_stop_or_park_observed']


def curb_extent(context):
    return {'start_x_m':context['start_x_m'], 'end_x_m':context['end_x_m'],
            'paint_color':context['paint_color']}


def footage_join(frame_map):
    return all(set(row['views']) == VIEWS for row in frame_map)


def statute_context(statutory):
    return {'law_id':statutory['law_id'],
            'text_sha256':statutory['law_text_sha256']}


def mail_clause_context(statutory):
    text=statutory['law_text']
    marker='(5) At locations where a drop box for U.S. mail'
    if marker not in text:
        raise ValueError('Frozen U.S. mail exception text absent')
    return text[text.index(marker):]


def scope_occupancy(observation):
    return observation['red_curb_stop_or_park_observed']


def signed_context(observation):
    return observation


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; use fresh saved attempt')
    for name in ('construction.json','config.json','assignment-source.json',
                 'statutory-context.json',
                 'red-curb-road.xodr','native-map-readback.json',
                 'native-raw-actors.jsonl','native-passenger-inventory.jsonl',
                 'video_frames.jsonl','trace.jsonl',
                 'capture/evidence.jsonl'):
        source(attempt,name)
    for view in VIEWS:
        source(attempt,view+'.mkv')
    config=json.loads(source(attempt,'config.json').read_text())
    construction=json.loads(source(attempt,'construction.json').read_text())
    assignment=json.loads(source(attempt,'assignment-source.json').read_text())
    statutory=json.loads(source(attempt,'statutory-context.json').read_text())
    map_readback=json.loads(source(attempt,'native-map-readback.json').read_text())
    context=paint_context(map_readback)
    actor_rows=rows(attempt,'native-raw-actors.jsonl')
    frame_map=rows(attempt,'video_frames.jsonl')
    trace=rows(attempt,'trace.jsonl')
    walker_rows=rows(attempt,'native-passenger-inventory.jsonl')
    expected_frames=config.get('capture_frames')
    if type(expected_frames) is not int or expected_frames < 2:
        raise ValueError('Missing long exception capture schedule')
    schedule=duration_plan({'case_id':config['case_id'],
        'requested_stationary_duration_s':config.get('requested_stationary_duration_s')},
        approach_frames=config.get('requested_approach_frames'))
    if expected_frames!=schedule['capture_frames'] or \
       config.get('requested_boundary')!=schedule['requested_boundary']:
        raise ValueError('Long exception capture schedule differs')
    if config.get('activity_request') is not None:
        raise ValueError('No-loading case has an activity request')
    activity=derive_passenger_absence(walker_rows,actor_rows,
                                     schedule['stationary_first_frame'])
    if construction['case_id'] != config['selected_case_id'] or \
       config['case_id'] != config['selected_case_id'] or \
       assignment.get('law_id') != config['law_id'] or \
       sha(attempt/'red-curb-road.xodr') != config['road_sha256']:
        raise ValueError('Selected red-curb case or frozen source differs')
    if statutory.get('assignment_id')!=assignment['assignment_id'] or \
       statutory.get('law_id')!=assignment['law_id'] or \
       statutory.get('law_text')!=assignment['law']['text'] or \
       statutory.get('law_text_sha256')!=hashlib.sha256(
           assignment['law']['text'].encode()).hexdigest():
        raise ValueError('Acquired statutory context differs from frozen assignment')
    if len(actor_rows) != len(frame_map) or len(trace) != expected_frames:
        raise ValueError('Missing synchronized saved trace')
    blueprints={row.get('blueprint') for row in actor_rows}
    if blueprints != {config.get('native_blueprint')}:
        raise ValueError('Native vehicle blueprint differs from exact case')
    speeds=[]
    for i,row in enumerate(actor_rows):
        velocity=row.get('velocity_native_xyz_mps')
        if not isinstance(velocity,list) or len(velocity)!=3 or not all(
                isinstance(v,(int,float)) and math.isfinite(v) for v in velocity):
            raise ValueError('Missing original or explicitly synthetic Native velocity')
        if trace[i].get('frame')!=row['native_frame'] or \
           frame_map[i].get('carla_frame')!=row['native_frame']:
            raise ValueError('Saved trace/frame identity differs')
        speeds.append(math.sqrt(sum(v*v for v in velocity)))
    observation=measure(actor_rows,frame_map,context,expected_frames=expected_frames)
    authored=read_road(source(attempt,'red-curb-road.xodr').read_text())
    sign=map_readback.get('sign_readback')
    if sign != authored['sign_readback'] and not (
        isinstance(sign,dict) and
        {key:sign.get(key) for key in authored['sign_readback']} ==
            authored['sign_readback'] and
        map_readback.get('source_kind')=='native_readback' and
        sign.get('native_signal_id')=='15014201'):
        raise ValueError('Missing source-bound signed-curb readback')
    if sign['displayed_classes'] != config.get('sign_classes'):
        raise ValueError('Signed-curb class differs from exact case')
    exception=measure_exception(actor_rows,{
        'source_kind':actor_rows[0]['source_kind'],
        'red_curb':{'paint_color':context['paint_color'],
            'start_x_m':context['start_x_m'],
            'end_x_m':context['end_x_m'],'curb_y_m':context['curb_y_m']},
        'sign_readback':sign,
        'vehicle_readback':{'native_blueprint':next(iter(blueprints)),
            'declared_service_class':config['service_class']},
        'mailbox_readback':map_readback.get('mailbox_readback')},activity)
    expected_activity=config.get('activity_request')
    if expected_activity is not None and not any(
            item['name']==expected_activity for item in exception['recorded_activity_events']):
        raise ValueError('Missing source-bound requested activity event')
    if exception['recorded_activity_events']:
        raise ValueError('No-loading case contains a recorded activity event')
    hashes={name:sha(attempt/name) for name in
            ('statutory-context.json','native-map-readback.json',
             'native-raw-actors.jsonl','video_frames.jsonl',
             'native-passenger-inventory.jsonl')}
    measurements={
        'signed_curb_observation':{'method':'signed_context',
            'value':signed_context(exception),
            'sources':{name:hashes[name] for name in
                ('native-raw-actors.jsonl','native-map-readback.json',
                'native-passenger-inventory.jsonl')}},
        'red_curb_stop_or_park_observed':{
            'method':'red_occupancy','value':red_occupancy(observation),
            'sources':{name:hashes[name] for name in
                       ('native-raw-actors.jsonl','video_frames.jsonl','native-map-readback.json')}},
        'red_curb_extent':{'method':'curb_extent','value':curb_extent(context),
                            'sources':{'native-map-readback.json':hashes['native-map-readback.json']}},
        'four_view_frame_join':{'method':'footage_join','value':footage_join(frame_map),
                                'sources':{'video_frames.jsonl':hashes['video_frames.jsonl']}},
        'statute_source_context':{'method':'statute_context','value':statute_context(statutory),
                                   'sources':{'statutory-context.json':hashes['statutory-context.json']}},
        'mail_exception_source_text':{'method':'mail_clause_context',
            'value':mail_clause_context(statutory),
            'sources':{'statutory-context.json':hashes['statutory-context.json']}},
        'scope_red_occupancy':{'method':'scope_occupancy',
            'value':scope_occupancy(observation),
            'sources':{name:hashes[name] for name in
                       ('native-raw-actors.jsonl','video_frames.jsonl','native-map-readback.json')}}}
    channels=attempt/'channels'; channels.mkdir()
    stopped_ids=set(observation['red_curb_stopped_frame_ids'])
    values={
        'ego_pose':[{'center_xy_m':r['ego_center_native_xy_m'],
                     'body_xy_m':r['ego_body_native_xy_m'],
                     'heading_deg':r['yaw_deg']} for r in actor_rows],
        'ego_speed':speeds,
        'red_curb_stop_or_park':[
            i in stopped_ids for i in range(expected_frames)],
        'four_source_views':[True]*expected_frames}
    evidence=[]
    for channel in construction['recording_description']['channels']:
        name=channel['name']
        if name not in values:raise ValueError('Unexpected red-curb channel: '+name)
        path=channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':row['time_s'],'value':value},
                               allow_nan=False)+'\n' for row,value in zip(actor_rows,values[name])))
        evidence.append({'name':name,'unit':channel['unit'],
                         'reference':'channels/'+path.name})
    context_path=attempt/'red-curb-context.json'
    context_path.write_text(json.dumps({'red_curb_map_readback':{
        'source':'native-map-readback.json',
        'sha256':hashes['native-map-readback.json']}},indent=2)+'\n')
    evidence.append({'name':'red_curb_map_readback','unit':'structured',
                     'reference':context_path.name})
    result={'case_id':config['case_id'],
            'measured_values':{'red_curb_stop_or_park_observed':red_occupancy(observation),
                               'signed_curb_observation':{
                                   key:value for key,value in exception.items()
                                   if key != 'legal_verdict'},
                               'red_curb_stopped_frames':len(observation['red_curb_stopped_frame_ids'])},
            'target_checks':[{'target':'red-curb occupied while stopped',
                'requested':30<=config['requested_target_x_m']<=50,
                'measured':red_occupancy(observation),
                'method':'joined original body position and red paint readback',
                'tolerance':'source observation; no legal duration threshold',
                'matched':red_occupancy(observation)==
                    (30<=config['requested_target_x_m']<=50),
                'physical_cause_confirmed':False,
                'cause_evidence':['native-raw-actors.jsonl','native-map-readback.json']},
                {'target':'requested 30-minute duration boundary',
                 'requested':schedule['requested_boundary'],
                 'measured':exception['duration_relative_to_30_minutes'],
                 'method':'retained Native body and velocity interval at 20 Hz',
                 'tolerance':'frame grid; no legal exception determination',
                 'matched':exception['duration_relative_to_30_minutes']==
                     schedule['requested_boundary'],
                 'physical_cause_confirmed':False,
                 'cause_evidence':['native-raw-actors.jsonl',
                                   'native-map-readback.json']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':str(expected_frames)+' source frames; physical and legal review pending',
            'physical_failure_flags':['Original red paint and pixel visibility unreviewed'],
            'trace_reference':'trace.jsonl',
            'video_references':[view+'.mkv' for view in VIEWS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':construction['recording_description'],
            'recording_evidence':evidence,
            'realized_observables':{'red_curb_stopped_frames':{
                'value':len(observation['red_curb_stopped_frame_ids']),'unit':'count',
                'method':'retained Native body and curb geometry',
                'time_window':str(config['duration_s'])+' s source interval','statistic':'any stopped frame touching red',
                'reference':'native-raw-actors.jsonl'}},
            'provenance_kind':'synthetic_local_diagnostic' if observation['source_kind']==
                'synthetic_native_sample' else 'native',
            'accepted':False}
    from worker_exchange.native_output import write_result
    output.write_text(json.dumps({'format':'c150142-red-curb-saved-analysis-v1',
        'case_id':config['case_id'],'candidate_id':config['candidate_id'],
        'source_kind':observation['source_kind'],'measurements':measurements,
        'physical_acceptance_claimed':False,'legal_verdict_claimed':False},
        indent=2,allow_nan=False)+'\n')
    write_result(attempt,result)
    return measurements


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),sort_keys=True))
