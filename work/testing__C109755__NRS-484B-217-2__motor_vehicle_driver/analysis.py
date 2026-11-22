"""Saved-only source-bound stripe crossing measurements; no legal safety threshold."""
import argparse
import hashlib
import json
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


def measure(attempt):
    attempt=Path(attempt);acquisition=json.loads((attempt/'acquisition.json').read_text())
    history=source(attempt,acquisition,'turn-history.jsonl')
    zone=source(attempt,acquisition,'zone-context.json')
    rows=[json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    context=json.loads(zone.read_text())
    if not rows or context.get('zone_kind')!='marked_no_passing_zone' or context.get('striping_source')!='native_map':
        raise ValueError('marked zone or original turn history missing')
    stripe=context['stripe_y_m'];first=None;previous=None
    for row in rows:
        if previous and (row['frame']<=previous['frame'] or row['time_s']<=previous['time_s']):
            raise ValueError('original frame/time order invalid')
        if previous and previous['ego_center_y_m']<stripe<=row['ego_center_y_m'] and first is None:
            first=row
        previous=row
    if first is None:raise ValueError('no observed stripe crossing')
    if not all('left_signal' in row and 'oncoming_body_gap_m' in row and 'following_body_gap_m' in row for row in rows):
        raise ValueError('signal or traffic measurements missing')
    if any(row['oncoming_body_gap_m']<0 or row['following_body_gap_m']<0 for row in rows):
        raise ValueError('invalid traffic gap measurement')
    activated=[r for r in rows if r['left_signal'] and r['time_s']<=first['time_s']]
    return {'format':'worker-stripe-measurements','crossing_frame':first['frame'],
            'crossing_time_s':first['time_s'],'signal_started_s':activated[0]['time_s'] if activated else None,
            'signal_active_at_crossing':bool(first['left_signal']),
            'minimum_oncoming_body_gap_m':min(r['oncoming_body_gap_m'] for r in rows),
            'minimum_following_body_gap_m':min(r['following_body_gap_m'] for r in rows),
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
            'recording_description':{'summary':'Measured left-turn crossing of Native map marking'},
            'recording_evidence':[{'source':k,'sha256':v} for k,v in report['measurements']['left_turn_crossing_measurement']['sources'].items()],
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
