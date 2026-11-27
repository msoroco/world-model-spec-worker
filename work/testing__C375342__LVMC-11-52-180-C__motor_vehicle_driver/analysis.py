"""Saved-only original alley duration finalizer. No legal verdict is issued."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from alley_site import ASSIGNMENT,load_site
from alley_native import observed_intervals
from duration_measurement import measure_source_packet

SOURCES=('parking-history.jsonl','parking-intervals.json','alley-context.json',
         'video_frames.jsonl','trace.jsonl','reviewed-site/site.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def verified(attempt,name,acquisition):
    path=attempt/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    ref=acquisition.get(name,{})
    if ref.get('kind')!='original_native' or ref.get('sha256')!=sha(path):
        raise ValueError('missing or stale original Native source: '+name)
    return path


def measure_saved(attempt):
    attempt=Path(attempt)
    acquisition_path=attempt/'acquisition.json'
    acquisition=json.loads(acquisition_path.read_text())
    fixture=(attempt/'fixture-provenance.json').is_file()
    paths={name:verified(attempt,name,acquisition) for name in SOURCES}
    cfg=json.loads((attempt/'config.json').read_text())
    if cfg.get('assignment_id')!=ASSIGNMENT:
        raise ValueError('wrong exact assignment')
    site=json.loads(paths['reviewed-site/site.json'].read_text())
    for ref in site.get('sources',{}).values():
        verified(attempt,'reviewed-site/'+ref['path'],acquisition)
    load_site(paths['reviewed-site/site.json'],cfg['selected_case_id'])
    history=rows(paths['parking-history.jsonl'])
    mapping=rows(paths['video_frames.jsonl'])
    trace=rows(paths['trace.jsonl'])
    if not history or len(history)!=len(mapping) or len(trace)!=len(mapping):
        raise ValueError('original parking, camera and trace frame counts differ')
    if len(history)!=cfg['duration_s']*cfg['rate_hz'] and not fixture:
        raise ValueError('original rolling-hour capture duration differs from 20 Hz contract')
    for event,video,telemetry in zip(history,mapping,trace):
        if (event.get('frame')!=video.get('carla_frame') or event.get('frame')!=telemetry.get('frame') or
                event.get('native_time_s')!=video.get('time_s') or event.get('native_time_s')!=telemetry.get('time_s')):
            raise ValueError('original parking, camera and trace frame identities differ')
    context=json.loads(paths['alley-context.json'].read_text())
    if (context.get('assignment_id')!=ASSIGNMENT or context.get('case_id')!=cfg['selected_case_id'] or
            context.get('site_sha256')!=sha(paths['reviewed-site/site.json']) or
            any(row.get('vehicle_actor_id')!=context.get('vehicle_actor_id') or
                row.get('marking_actor_id')!=context.get('marking_actor_id') for row in history)):
        raise ValueError('original alley context, site or actor identity differs')
    interval_packet=json.loads(paths['parking-intervals.json'].read_text())
    if interval_packet.get('case_id')!=cfg['selected_case_id'] or interval_packet.get('vehicle_id')!=str(context['vehicle_actor_id']):
        raise ValueError('original interval packet case or vehicle differs')
    if interval_packet.get('requested_intervals_s')!=cfg['case']['requested_intervals_s']:
        raise ValueError('original interval request differs from exact construction')
    observed=observed_intervals(history,context['vehicle_actor_id'])
    if interval_packet.get('intervals')!=observed:
        raise ValueError('original interval packet differs from frame-derived parking state')
    inventory={name:acquisition[name] for name in ('parking-intervals.json','alley-context.json','video_frames.jsonl')}
    value=measure_source_packet(attempt,inventory)
    value['sources']={name:acquisition[name]['sha256'] for name in SOURCES}
    value['capture_source_sha256']=sha(acquisition_path)
    value['diagnostic_fixture']=fixture
    value['source_kind']='diagnostic_native_shape' if fixture else 'original_native'
    value['observed_interval_count']=len(observed)
    return value


def saved_result(attempt,value):
    from worker_exchange.native_output import physical_result,validate_result
    attempt=Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    description=construction['recording_description']
    history=rows(attempt/'parking-history.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    context=json.loads((attempt/'alley-context.json').read_text())
    channels=attempt/'channels'
    channels.mkdir(exist_ok=False)
    streams={
        'vehicle_parking_intervals':[{'parked_observed':r['parked_observed'],'position_xy':r['position_xy'],
                                      'speed_mps':r['speed_mps'],'control_state':r['control_state']} for r in history],
        'alley_and_angle_designation':[{'alley_source':context['municipal_alley_source'],
                                       'designation_source':context['engineer_designation_source'],
                                       'marking_source':context['angle_marking_source']}] * len(history),
        'otherwise_lawful_parking':[{'source':context['other_parking_rules_source']}] * len(history),
        'rolling_hour_maximum_seconds':[value['maximum_parked_seconds_in_any_hour']] * len(history),
        'history_completeness':[{'status':value['source_history_status']}] * len(history),
        'camera_frame_identity':mapping,
    }
    evidence=[]
    for channel in description['channels']:
        name=channel['name']
        if name not in streams:
            raise ValueError('unsupported alley-duration channel: '+name)
        path=channels/(name+'.jsonl')
        with path.open('x',encoding='utf-8') as stream:
            for event,sample in zip(history,streams[name]):
                stream.write(json.dumps({'time_s':event['native_time_s'],'value':sample},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':str(path.relative_to(attempt))})
    context_path=channels/'context.json'
    context_path.write_text(json.dumps({'original_alley_designation_and_lawfulness':context,
                                        'rolling_hour_measurement':value},allow_nan=False)+'\n')
    for item in description['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':str(context_path.relative_to(attempt))})
    actual=value['observed_interval_count']>0
    result={'case_id':cfg['selected_case_id'],'measured_values':value,
            'target_checks':[{'target':'original otherwise-lawful alley parking interval in designated angle space',
                              'requested':True,'measured':actual,
                              'method':'original source-gated frame-derived parked intervals and 3600-second rolling aggregation',
                              'tolerance':0,'matched':actual,'physical_cause_confirmed':False,
                              'cause_evidence':value['sources']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'Saved physical and legal review pending','physical_failure_flags':[],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in ('overview','approach','reference_corner','driver_reference')],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
            'recording_evidence':evidence,'realized_observables':{}}
    result=physical_result(attempt,result)
    validate_result(result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    value=measure_saved(args.attempt)
    result=saved_result(args.attempt,value)
    Path(args.attempt,'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    report={'format':'worker-analysis-report',
            'measurements':{'rolling_hour_parking_duration':{'value':value,'method':'measure_saved',
                                                               'sources':value['sources']}},
            'physical_checks':result['physical_checks'],
            'realized_observables':result['realized_observables'],
            'limitations':['Original municipal alley, designation, otherwise-lawful parking, complete vehicle history and actual pixels require independent review.'],
            'analysis_complete':True,'legal_verdict_claimed':False}
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
