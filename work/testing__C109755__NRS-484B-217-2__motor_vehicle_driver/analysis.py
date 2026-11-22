"""Saved-only source-bound stripe crossing measurements; no legal safety threshold."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source(attempt, acquisition, name):
    info=acquisition.get(name)
    path=attempt/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    if not info or info.get('kind')!='original_native' or not path.is_file() or sha(path)!=info.get('sha256'):
        raise ValueError('missing or stale original Native source: '+name)
    return path


def traffic_response(rows, crossing_time_s, traffic_speed, *, flank_s=2.0):
    """Describe physical traffic response around crossing without a legal cutoff."""
    before=[index for index,row in enumerate(rows)
            if crossing_time_s-flank_s<=row['time_s']<crossing_time_s]
    after=[index for index,row in enumerate(rows)
           if crossing_time_s<=row['time_s']<=crossing_time_s+flank_s]
    in_window=before+after
    maximum_gap=max((rows[b]['time_s']-rows[a]['time_s']
                     for a,b in zip(in_window,in_window[1:])),default=None)
    full_coverage=bool(before and after and
                       rows[0]['time_s']<=crossing_time_s-flank_s and
                       rows[-1]['time_s']>=crossing_time_s+flank_s and
                       maximum_gap is not None and maximum_gap<=0.1)
    result={'crossing_time_s':crossing_time_s,'flank_s':flank_s,
            'pre_sample_count':len(before),'crossing_and_post_sample_count':len(after),
            'maximum_sample_gap_s':maximum_gap,'full_window_observed':full_coverage,
            'participants':{}}
    for role in ('oncoming','following'):
        speeds=traffic_speed[role]['samples_mps']
        def summary(indices):
            if not indices:return None
            values=[speeds[index] for index in indices]
            gaps=[rows[index][role+'_body_gap_m'] for index in indices]
            return {'first_frame':rows[indices[0]]['frame'],
                    'last_frame':rows[indices[-1]]['frame'],
                    'mean_speed_mps':sum(values)/len(values),
                    'minimum_body_gap_m':min(gaps),
                    'speed_samples_mps':values,'body_gap_samples_m':gaps}
        pre=summary(before);post=summary(after)
        result['participants'][role]={
            'before':pre,'crossing_and_after':post,
            'mean_speed_change_mps':
                post['mean_speed_mps']-pre['mean_speed_mps'] if pre and post else None,
            'minimum_gap_change_m':
                post['minimum_body_gap_m']-pre['minimum_body_gap_m'] if pre and post else None}
    return result


def measure(attempt):
    attempt=Path(attempt);acquisition=json.loads((attempt/'acquisition.json').read_text())
    history=source(attempt,acquisition,'turn-history.jsonl')
    zone=source(attempt,acquisition,'zone-context.json')
    rows=[json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    context=json.loads(zone.read_text())
    if not rows or context.get('zone_kind')!='marked_no_passing_zone' or context.get('striping_source')!='native_map':
        raise ValueError('marked zone or original turn history missing')
    stripe=context['stripe_y_m'];first=None;previous=None
    def leading_y(row):
        vertices=row.get('ego_body_vertices_m')
        if not isinstance(vertices,list) or len(vertices)<4 or any(
            not isinstance(v,list) or len(v)<2 or
            any(type(component) not in (int,float) or not math.isfinite(component)
                for component in v[:2]) for v in vertices):
            raise ValueError('missing original ego body geometry')
        return max(v[1] for v in vertices)
    for row in rows:
        edge=leading_y(row)
        if previous and (row['frame']<=previous[0]['frame'] or row['time_s']<=previous[0]['time_s']):
            raise ValueError('original frame/time order invalid')
        if previous and previous[1]<stripe<=edge and first is None:
            first=row
        previous=(row,edge)
    if first is None:raise ValueError('no observed stripe crossing')
    if not all('left_signal' in row and 'oncoming_body_gap_m' in row and 'following_body_gap_m' in row for row in rows):
        raise ValueError('signal or traffic measurements missing')
    if any(type(row[role+'_body_gap_m']) not in (int,float) or
           not math.isfinite(row[role+'_body_gap_m']) or row[role+'_body_gap_m']<0
           for role in ('oncoming','following') for row in rows):
        raise ValueError('invalid traffic gap measurement')
    traffic_speed={}
    for role in ('oncoming','following'):
        speeds=[]
        for row in rows:
            vector=row.get(role+'_velocity_xy_mps')
            if not isinstance(vector,list) or len(vector)!=2 or any(
                    type(value) not in (int,float) or not math.isfinite(value) for value in vector):
                raise ValueError('missing original '+role+' velocity history')
            speeds.append(math.hypot(*vector))
        traffic_speed[role]={'minimum_mps':min(speeds),'maximum_mps':max(speeds),
                             'observed_range_mps':max(speeds)-min(speeds),
                             'samples_mps':speeds}
    activated=[r for r in rows if r['left_signal'] and r['time_s']<=first['time_s']]
    # Count a continuous signal run ending at the turn onset, using observed
    # center positions. No district or legal safety claim follows from this.
    onset=next((i for i,r in enumerate(rows) if r.get('ego_center_x_m',float('-inf'))>=
                context.get('crossing_x_m',0)-4),None)
    signal_distance=None
    if onset is not None and all(type(r.get('ego_center_x_m')) in (int,float) and
                                 type(r.get('ego_center_y_m')) in (int,float) and
                                 math.isfinite(r['ego_center_x_m']) and math.isfinite(r['ego_center_y_m'])
                                 for r in rows[:onset+1]):
        start=onset
        while start>=0 and rows[start]['left_signal'] is True:start-=1
        start+=1
        signal_distance=sum(math.hypot(b['ego_center_x_m']-a['ego_center_x_m'],
                                      b['ego_center_y_m']-a['ego_center_y_m'])
                            for a,b in zip(rows[start:onset],rows[start+1:onset+1])) if start<onset else 0.0
    return {'format':'worker-stripe-measurements','crossing_frame':first['frame'],
            'crossing_time_s':first['time_s'],'signal_started_s':activated[0]['time_s'] if activated else None,
            'signal_active_at_crossing':bool(first['left_signal']),
            'continuous_signal_before_turn_m':signal_distance,
            'signal_300ft_observed':signal_distance is not None and signal_distance>=300*0.3048,
            'crossing_method':'first sampled original ego body edge over stripe after wholly-below sample',
            'minimum_oncoming_body_gap_m':min(r['oncoming_body_gap_m'] for r in rows),
            'minimum_following_body_gap_m':min(r['following_body_gap_m'] for r in rows),
            'traffic_speed_observations':traffic_speed,
            'traffic_response_window':traffic_response(rows,first['time_s'],traffic_speed),
            'zone_context_sha256':acquisition['zone-context.json']['sha256'],
            'turn_history_sha256':acquisition['turn-history.jsonl']['sha256'],
            'legal_safety_and_impediment':'unresolved'}


def build_report(attempt):
    attempt=Path(attempt)
    value=measure(attempt)
    sources={name:sha(attempt/name) for name in ('turn-history.jsonl','zone-context.json')}
    return {'format':'worker-analysis-report','measurements':{
        'left_turn_crossing_measurement':{'value':value,'method':'measure','sources':sources}},
        'limitations':['Statutory zone extent, subsection 3/4 applicability, safety and impediment remain unresolved.'],
        'analysis_complete':True,'legal_verdict_claimed':False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    cfg=json.loads((Path(attempt)/'config.json').read_text())
    construction=json.loads((Path(attempt)/'construction.json').read_text())
    planned=construction['recording_description']
    acquisition=json.loads((Path(attempt)/'acquisition.json').read_text())
    history=source(Path(attempt),acquisition,'turn-history.jsonl')
    rows=[json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    channel_fields={'ego_body_history':'ego_body_vertices_m',
                    'signal_history':'left_signal',
                    'oncoming_history':'oncoming_body_vertices_m',
                    'following_history':'following_body_vertices_m'}
    channels=Path(attempt)/'channels'
    channels.mkdir(exist_ok=True)
    recording=[]
    for channel in planned['channels']:
        name=channel['name']
        if name=='stripe_geometry':
            continue  # The source-bound static geometry is emitted below.
        if name not in channel_fields:
            raise ValueError('Unsupported declared recording channel: '+name)
        field=channel_fields[name]
        if any(field not in row for row in rows):
            raise ValueError('Missing original recording channel: '+field)
        path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s':row['time_s'],'value':row[field]},allow_nan=False)+'\n')
        recording.append({'name':name,'unit':channel['unit'],'reference':str(path.relative_to(attempt))})
    zone=source(Path(attempt),acquisition,'zone-context.json')
    context=json.loads(zone.read_text())
    context_file=channels/'stripe_geometry.jsonl'
    stripe_value={'zone_context_sha256':sha(zone),
                  'stripe_y_m':context['stripe_y_m'],
                  'crossing_x_m':context['crossing_x_m'],
                  'authority_source_sha256':context.get('authority_source_sha256'),
                  'zone_extent_verified':context.get('zone_extent_verified')}
    with context_file.open('x') as stream:
        for row in rows:
            stream.write(json.dumps({'time_s':row['time_s'],'value':stripe_value},
                                    allow_nan=False)+'\n')
    recording.append({'name':'stripe_geometry','unit':'structured record',
                      'reference':str(context_file.relative_to(attempt))})
    measured=report['measurements']['left_turn_crossing_measurement']['value']
    target={'target':'observed left-turn stripe crossing','requested':True,'measured':True,
            'method':'measure','tolerance':0,'matched':True,'physical_cause_confirmed':False,
            'cause_evidence':report['measurements']['left_turn_crossing_measurement']['sources']}
    result={'case_id':cfg['selected_case_id'],'measured_values':measured,
            'target_checks':[target],'setup_confirmed':False,'behavior_attempted':False,
            'maneuver_completed':False,'termination_reason':'Saved measurements pending physical assessment',
            'physical_failure_flags':[],'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':planned,
            'recording_evidence':recording,
            'realized_observables':{}}
    result=physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=build_report(args.attempt)
    result=saved_result(args.attempt,report)
    report['physical_checks']=result['physical_checks']
    report['realized_observables']=result['realized_observables']
    with Path(args.attempt,'result.json').open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
