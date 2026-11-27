"""Saved-only green-arrow source analysis; no legal or physical acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from arrow_measure import measure
from capture import derive_channels

SOURCES=('intersection-context.json','signal_frames.jsonl','motion_frames.jsonl',
         'native.jsonl','video_frames.jsonl')
VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def required(folder,name):
    path=Path(folder)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arrow_program_source(facts):
    return {'arrow_program_frames':facts['arrow_program_frames'],
            'unknown_original_arrow_pixel_frames':facts['unknown_original_arrow_pixel_frames'],
            'arrow_pixel_review_pending':facts['arrow_pixel_review_pending'],
            'first_unlit_intersection_motion_frame':facts['first_unlit_intersection_motion_frame']}


def direction_and_entry_source(facts):
    return {'first_ego_entry_frame':facts['first_ego_entry_frame'],
            'first_direction_mismatch_frame':facts['first_direction_mismatch_frame']}


def participant_priority_source(facts):
    return {'first_pedestrian_crosswalk_motion_overlap_frame':facts['first_pedestrian_crosswalk_motion_overlap_frame'],
            'first_other_traffic_motion_overlap_frame':facts['first_other_traffic_motion_overlap_frame']}


def analysis_report(folder):
    folder=Path(folder)
    config=json.loads(required(folder,'config.json').read_text())
    paths={name:required(folder,name) for name in SOURCES}
    facts=measure(folder)
    if facts['frames']!=600 or config['case_id']!=config['selected_case_id']:
        raise ValueError('Exact selected green-arrow source differs')
    methods={
        'arrow_program_source':(arrow_program_source,
            ('signal_frames.jsonl','intersection-context.json')),
        'direction_and_entry_source':(direction_and_entry_source,
            ('motion_frames.jsonl','signal_frames.jsonl','intersection-context.json')),
        'participant_priority_source':(participant_priority_source,
            ('motion_frames.jsonl','intersection-context.json')),
    }
    return {'format':'worker-c111603-arrow-analysis-v1',
            'case_id':config['selected_case_id'],'analysis_complete':True,
            'legal_verdict_claimed':False,'physical_acceptance_claimed':False,
            'measurements':{name:{'method':name,'value':method(facts),
                'sources':{source:sha(paths[source]) for source in inputs}}
                for name,(method,inputs) in methods.items()},
            'limitations':['Original pixels must independently establish a governed green turn arrow alone.',
                           'Participant positions alone do not establish lawful right-of-way.',
                           'Motion overlap is an engineering timing observation, not a yielding verdict.']}


def finalize(attempt,output):
    from worker_exchange.native_output import physical_result,provenance_record,write_result
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use fresh analysis output and retain original sources')
    config=json.loads(required(attempt,'config.json').read_text())
    if config.get('rate_hz')!=20 or config.get('duration_s')!=30:
        raise ValueError('Exact 600-frame green-arrow source contract changed')
    report=analysis_report(attempt)
    facts=measure(attempt)
    provenance=provenance_record(attempt)
    original=provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    result={'case_id':config['selected_case_id'],'measured_values':facts,
        'target_checks':[{'target':'governed green-arrow direction and priority',
            'requested':config['selected_case_id'].rsplit('__',1)[-1],
            'measured':{key:facts[key] for key in (
                'first_ego_entry_frame','first_direction_mismatch_frame',
                'first_unlit_intersection_motion_frame',
                'first_pedestrian_crosswalk_motion_overlap_frame',
                'first_other_traffic_motion_overlap_frame')},
            'method':'source-joined original signal, motion and intersection geometry',
            'tolerance':'source diagnostic only; legal judgments pending',
            'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':list(SOURCES)}],
        'setup_confirmed':False,'behavior_attempted':original,
        'maneuver_completed':False,
        'termination_reason':'independent governing-head and lawful-priority review pending',
        'physical_failure_flags':['governing_head_pixels_review_pending',
                                  'participant_lawfulness_and_yield_review_pending'],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':derive_channels(attempt),
        'realized_observables':{'first_ego_entry_frame':{
            'value':facts['first_ego_entry_frame'],'unit':'frame',
            'method':'source-joined original ego center within surveyed intersection',
            'time_window':'600 frames','statistic':'first occurrence',
            'reference':'motion_frames.jsonl'}},
        'accepted':False,'legal_verdict_claimed':False}
    write_result(attempt,physical_result(attempt,result))
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
