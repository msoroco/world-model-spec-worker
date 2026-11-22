"""Saved-only physical measurements for a sole straight-arrow approach."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from runner import body_bounds, overlaps, require_sole_straight_arrow

SOURCES=('signal-head-history.jsonl','ego-body-history.jsonl',
         'participant-history.jsonl','intersection-context.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(attempt,name,acquisition):
    path=Path(attempt)/name
    info=acquisition.get(name,{})
    if not path.is_file():raise ValueError('Missing required source: '+name)
    if info.get('kind')!='original_native' or info.get('sha256')!=sha(path):
        raise ValueError('missing or stale original Native source: '+name)
    return path


def rows(path):
    value=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not value:raise ValueError('empty original history: '+Path(path).name)
    return value


def measure(attempt):
    attempt=Path(attempt)
    acquisition=json.loads((attempt/'acquisition.json').read_text())
    paths={name:verified(attempt,name,acquisition) for name in SOURCES}
    signals=rows(paths['signal-head-history.jsonl'])
    ego=rows(paths['ego-body-history.jsonl'])
    traffic=rows(paths['participant-history.jsonl'])
    context=json.loads(paths['intersection-context.json'].read_text())
    for name in ('facing_head_id','stop_line_x_m','intersection_bounds_m','adjacent_crosswalk_bounds_m'):
        if name not in context:raise ValueError('missing original intersection context: '+name)
    if len({len(signals),len(ego),len(traffic)})!=1:
        raise ValueError('original signal, ego and participant frame counts differ')
    first_arrow=None;first_entry=None;occupied_frames=[];unresolved=[];violated_hold=[]
    headings=[];previous=None
    for signal,body,participants in zip(signals,ego,traffic):
        identity=(signal.get('frame'),signal.get('time_s'))
        if identity!=(body.get('frame'),body.get('time_s')) or identity!=(participants.get('frame'),participants.get('time_s')):
            raise ValueError('original signal/ego/participant frame join changed')
        if previous and (identity[0]<=previous[0] or identity[1]<=previous[1]):
            raise ValueError('original frame/time order invalid')
        previous=identity
        if signal.get('facing_head_id')!=context['facing_head_id']:
            raise ValueError('signal head is not the ego-facing head')
        aspect=signal.get('aspect',{})
        arrow=bool(aspect.get('illuminated_indications')==[
            {'color':'green','shape':'arrow','direction':'straight'}])
        if arrow:
            require_sole_straight_arrow(aspect,head_id=context['facing_head_id'],frame=identity[0])
            if first_arrow is None:first_arrow=identity
        vertices=body.get('body_vertices_m')
        left,bottom,right,top=body_bounds(vertices)
        heading=body.get('heading_deg')
        if type(heading) not in (int,float) or not math.isfinite(heading):
            raise ValueError('missing original ego heading')
        headings.append(heading)
        if right>=context['intersection_bounds_m'][0] and first_entry is None:
            first_entry=identity
        if first_arrow is None:continue
        present=[]
        for person in participants.get('participants',[]):
            if not {'id','role','body_vertices_m','lawfully_present','lawful_presence_source'}<=person.keys():
                raise ValueError('participant source or lawful presence missing')
            if not person['lawful_presence_source']:
                raise ValueError('lawful presence lacks source')
            footprint=person['body_vertices_m']
            body_bounds(footprint)
            regions=[context['intersection_bounds_m'],*context['adjacent_crosswalk_bounds_m']]
            if person['lawfully_present'] and any(overlaps(footprint,r) for r in regions):
                present.append(person['id'])
        if present:
            occupied_frames.append({'frame':identity[0],'time_s':identity[1],'participant_ids':present})
            if right>context['stop_line_x_m']:
                violated_hold.append(identity[0])
        if right>=context['intersection_bounds_m'][0] and not arrow:
            unresolved.append(identity[0])
    return {'format':'worker-straight-arrow-measurements',
            'first_sole_arrow_frame':first_arrow[0] if first_arrow else None,
            'first_sole_arrow_time_s':first_arrow[1] if first_arrow else None,
            'first_ego_intersection_entry_frame':first_entry[0] if first_entry else None,
            'first_ego_intersection_entry_time_s':first_entry[1] if first_entry else None,
            'lawfully_occupied_frames':occupied_frames,
            'ego_past_stop_line_during_occupancy_frames':violated_hold,
            'entry_without_verified_arrow_frames':unresolved,
            'observed_heading_change_deg':(headings[-1]-headings[0]+180)%360-180,
            'sources':{name:acquisition[name]['sha256'] for name in SOURCES},
            'legal_yield_and_turn_interpretation':'unresolved'}


def measure_arrow(attempt):
    value=measure(attempt)
    return {key:value[key] for key in ('first_sole_arrow_frame','first_sole_arrow_time_s',
              'first_ego_intersection_entry_frame','entry_without_verified_arrow_frames')}


def measure_yield(attempt):
    value=measure(attempt)
    return {key:value[key] for key in ('lawfully_occupied_frames',
              'ego_past_stop_line_during_occupancy_frames','observed_heading_change_deg')}


def build_report(attempt):
    value=measure(attempt)
    return {'format':'worker-analysis-report',
            'measurements':{'straight_arrow_yield_measurement':{
                'value':value,'method':'measure','sources':value['sources']},
                'sole_arrow_measurement':{'value':measure_arrow(attempt),'method':'measure_arrow',
                    'sources':{name:value['sources'][name] for name in
                               ('signal-head-history.jsonl','ego-body-history.jsonl','intersection-context.json')}},
                'yield_measurement':{'value':measure_yield(attempt),'method':'measure_yield',
                    'sources':value['sources']}},
            'limitations':['Arrow asset, lawful presence and legal yielding require independent source review.'],
            'analysis_complete':True,'legal_verdict_claimed':False}


def saved_result(attempt,report):
    from worker_exchange.native_output import physical_result,validate_result
    attempt=Path(attempt)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    planned=construction['recording_description']
    acquisition=json.loads((attempt/'acquisition.json').read_text())
    signals=rows(verified(attempt,'signal-head-history.jsonl',acquisition))
    ego=rows(verified(attempt,'ego-body-history.jsonl',acquisition))
    traffic=rows(verified(attempt,'participant-history.jsonl',acquisition))
    context=json.loads(verified(attempt,'intersection-context.json',acquisition).read_text())
    output=attempt/'channels';output.mkdir(exist_ok=True)
    streams={
      'signal_head_history':[(row['time_s'],row['aspect']) for row in signals],
      'ego_body_history':[(row['time_s'],{'body_vertices_m':row['body_vertices_m'],
                                         'heading_deg':row['heading_deg']}) for row in ego],
      'vehicle_body_history':[(row['time_s'],[p for p in row['participants'] if p['role']=='vehicle']) for row in traffic],
      'pedestrian_body_history':[(row['time_s'],[p for p in row['participants'] if p['role']=='pedestrian']) for row in traffic],
    }
    evidence=[]
    for channel in planned['channels']:
        name=channel['name']
        if name not in streams:raise ValueError('Unsupported declared recording channel: '+name)
        path=output/(name+'.jsonl')
        with path.open('x') as stream:
            for time_s,value in streams[name]:
                stream.write(json.dumps({'time_s':time_s,'value':value},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':str(path.relative_to(attempt))})
    context_value={'intersection_geometry':{'intersection_bounds_m':context['intersection_bounds_m'],
                                            'stop_line_x_m':context['stop_line_x_m']},
                   'crosswalk_geometry':context['adjacent_crosswalk_bounds_m'],
                   'lawful_presence_context':{'source':'original participant history and phase context',
                     'source_sha256':acquisition['participant-history.jsonl']['sha256']}}
    context_path=output/'context.json'
    with context_path.open('x') as stream:stream.write(json.dumps(context_value,allow_nan=False)+'\n')
    for item in planned['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],
                         'reference':str(context_path.relative_to(attempt))})
    entered=report['measurements']['straight_arrow_yield_measurement']['value']['first_ego_intersection_entry_frame'] is not None
    result={'case_id':config['selected_case_id'],
            'measured_values':report['measurements']['straight_arrow_yield_measurement']['value'],
            'target_checks':[{'target':'observed straight intersection entry','requested':True,
                              'measured':entered,
                              'method':'measure','tolerance':0,'matched':entered,
                              'physical_cause_confirmed':False,
                              'cause_evidence':report['measurements']['straight_arrow_yield_measurement']['sources']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'Saved source assessment pending physical review',
            'physical_failure_flags':[],'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':planned,'recording_evidence':evidence,'realized_observables':{}}
    result=physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=build_report(args.attempt)
    result=saved_result(args.attempt,report)
    report['physical_checks']=result['physical_checks']
    report['realized_observables']=result['realized_observables']
    with (Path(args.attempt)/'result.json').open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
