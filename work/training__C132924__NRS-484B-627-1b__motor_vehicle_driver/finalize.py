"""Saved-only source analysis of roundabout lane and passing observations."""

import argparse
import hashlib
import json
from pathlib import Path

from capture import derive_channels
from measure import measure

SOURCES = ('native.jsonl','video_frames.jsonl','geometry.json')
VIDEOS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def required(folder,name):
    path = Path(folder)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def roundabout_lane_and_pass(folder,paths):
    return measure(Path(folder)/'config.json',*paths)


def impeding_source(facts):
    return {'follower_behind_frames':facts['counts']['follower_behind'],
            'ego_slower_frames':facts['counts']['ego_slower_than_follower'],
            'statutory_impeding_judgment':facts['impeding_judgment']}


def lane_occupancy_source(facts):
    return {key:facts['counts'][key] for key in
            ('extreme_right','inner_left','outside_or_straddling')}


def passing_source(facts):
    return {'slower_vehicle_ahead_frames':facts['counts']['slower_vehicle_ahead'],
            'pass_in_progress_frames':facts['counts']['pass_in_progress'],
            'necessity_judgment':facts['passing_necessity_judgment']}


def post_pass_source(facts):
    return {'first_clearance_frame':facts['first_clearance_frame'],
            'after_pass_right_frames':facts['counts']['after_pass_right'],
            'after_pass_left_frames':facts['counts']['after_pass_left']}


def analysis_report(folder):
    folder = Path(folder)
    config = json.loads(required(folder,'config.json').read_text())
    paths = [required(folder,name) for name in SOURCES]
    observed = roundabout_lane_and_pass(folder,paths)
    if observed['case_id'] != config['selected_case_id'] or observed['frames'] != 600:
        raise ValueError('Exact selected roundabout source differs')
    suffix = config['case_id'].rsplit('__',1)[-1]
    if suffix in ('necessary_pass','post_pass_linger') and observed['counts']['slower_vehicle_ahead']==0:
        raise ValueError('Original slower-vehicle pass source absent')
    functions = {'impeding_source':impeding_source,'lane_occupancy_source':lane_occupancy_source,
                 'passing_source':passing_source,'post_pass_source':post_pass_source}
    methods = ('impeding_source','lane_occupancy_source') if suffix in ('probe_a','probe_b') else (
        'impeding_source','passing_source','post_pass_source')
    return {'format':'worker-c132924-roundabout-analysis-v1',
            'case_id':config['selected_case_id'],'analysis_complete':True,
            'legal_verdict_claimed':False,
            'measurements':{method:{'method':method,'value':functions[method](observed),
                'sources':{name:sha(folder/name) for name in SOURCES}}
                for method in methods},
            'limitations':['Speed ordering and trailing position do not settle statutory impeding.',
                           'Controller requests do not establish pass necessity or lawful duration.',
                           'Original marked lane, body, slower-vehicle and pixel sources require independent review.']}


def finalize(attempt,output):
    from worker_exchange.native_output import physical_result,provenance_record,write_result
    attempt,output = Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use fresh analysis path and retain original sources')
    config = json.loads(required(attempt,'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('Exact 600-frame source contract changed')
    report = analysis_report(attempt)
    facts = roundabout_lane_and_pass(attempt,[attempt/name for name in SOURCES])
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    result = {
        'case_id':config['selected_case_id'],'measured_values':facts,
        'target_checks':[{'target':'extreme-right lane during impeding, except necessary passing',
            'requested':config['selected_case_id'].rsplit('__',1)[-1],
            'measured':{'lane_counts':{key:facts['counts'][key] for key in
                ('extreme_right','inner_left','outside_or_straddling')},
                'first_pass_frame':facts['first_pass_frame'],
                'first_clearance_frame':facts['first_clearance_frame']},
            'method':'original frame-joined Native body, lane, follower and slower vehicle sources',
            'tolerance':'engineering source diagnostic only; statutory judgment pending',
            'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':list(SOURCES)}],
        'setup_confirmed':False,'behavior_attempted':original,
        'maneuver_completed':False,
        'termination_reason':'independent physical and statutory source review pending',
        'physical_failure_flags':['marked_lane_and_body_review_pending',
                                  'impeding_and_passing_necessity_review_pending'],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':derive_channels(attempt),
        'realized_observables':{'extreme_right_frames':{
            'value':facts['counts']['extreme_right'],'unit':'frames',
            'method':'source-joined Native body occupancy','time_window':'600 frames',
            'statistic':'count','reference':'native.jsonl'}},
        'accepted':False,'legal_verdict_claimed':False}
    result = physical_result(attempt,result)
    write_result(attempt,result)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
