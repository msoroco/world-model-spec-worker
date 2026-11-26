"""Recorded-only raw separator finalizer; no legal crossing conclusion."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_separator import measure

VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
SOURCES=('separator-context.json','native-motion.jsonl','video_frames.jsonl')


def required(root,name):
    path=Path(root)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_prohibition(observed,context):
    return {'solid_white_separator':observed['separator'],
        'body_straddle_frame_count':observed['body_straddle_frame_count'],
        'first_body_straddle_frame':observed['first_body_straddle_frame'],
        'first_traffic_side_center_frame':observed['first_traffic_side_center_frame'],
        'official_context_review_pending':observed['source_context_review_pending'],
        'legal_verdict_claimed':False}


def measure_emergency(observed,context):
    return {'emergency_necessity_reviewed':observed['emergency_necessity_reviewed'],
        'obstruction_present':observed['emergency_obstruction_present'],
        'minimum_obstruction_center_distance_m':observed['minimum_obstruction_center_distance_m'],
        'source_status':'reviewed' if observed['emergency_necessity_reviewed'] else 'review_pending',
        'legal_verdict_claimed':False}


def measure_subsection_3(observed,context):
    return {'subsection_3_conditions_reviewed':observed['subsection_3_conditions_reviewed'],
        'supplied_cross_reference':'subsection 1(c)(1) paved shoulder use',
        'automatic_2b_crossing_permission_assumed':False}


def measure_shoulder_context(observed,context):
    return {'shoulder_permission_treated_as_crossing_authorization':False,
        'vehicle_driver_scope_reviewed':observed['vehicle_driver_scope_reviewed'],
        'vehicle_class_and_signage_review_pending':True}


METHODS=(('separator_geometry','measure_prohibition',measure_prohibition),
         ('emergency_context','measure_emergency',measure_emergency),
         ('subsection_3_context','measure_subsection_3',measure_subsection_3),
         ('shoulder_context','measure_shoulder_context',measure_shoulder_context))


def finalize(attempt,output):
    from worker_exchange.native_output import provenance_record,write_result
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use fresh saved-only analysis output')
    cfg=json.loads(required(attempt,'config.json').read_text())
    context=json.loads(required(attempt,'separator-context.json').read_text())
    observed=measure(attempt)
    hashes={name:sha(required(attempt,name)) for name in SOURCES}
    provenance=provenance_record(attempt)
    native=provenance['provenance_kind']=='native' and not provenance['diagnostic_fixture']
    target=cfg.get('case_suffix')
    matched=(observed['body_straddle_frame_count']==0 if target=='controlled_1' else
             observed['body_straddle_frame_count']>0 and observed['first_traffic_side_center_frame'] is not None)
    result={'case_id':cfg['case_id'],'measured_values':observed,
        'target_checks':[{'target':target,'requested':cfg.get('target'),
            'measured':measure_prohibition(observed,context),
            'method':'same-tick original full-body geometry and lane history',
            'tolerance':'raw geometry only; no statutory crossing cutoff',
            'matched':matched,'physical_cause_confirmed':False,
            'cause_evidence':list(SOURCES)}],
        'setup_confirmed':native and not observed['source_context_review_pending'],
        'behavior_attempted':native,'maneuver_completed':native and matched,
        'termination_reason':'600 source frames retained',
        'physical_failure_flags':['legal_controlled_access_and_line_authority_review_pending'] if observed['source_context_review_pending'] else [],
        'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':cfg['recording_description'],
        'recording_evidence':[{'name':name,'unit':'structured','reference':'separator-context.json'}
            for name in ('st.lane_marking','st.controlled_access','st.shoulder','ru.emergency_vehicle','ru.transit_bus')]+
            [{'name':name,'unit':'structured','reference':'native-motion.jsonl'}
            for name in ('drv.straddles_marking','drv.lane_change','rel.occupies')],
        'realized_observables':{'body_straddle_frame_count':{'value':observed['body_straddle_frame_count'],
            'unit':'frames','method':'original body versus solid line','time_window':'600 frames',
            'statistic':'count','reference':'native-motion.jsonl'}},
        'provenance_kind':provenance['provenance_kind'],
        'diagnostic_fixture':provenance['diagnostic_fixture'],
        'accepted':False,'legal_verdict_claimed':False}
    write_result(attempt,result)
    measurements={key:{'method':method,'value':function(observed,context),
        'sources':dict(hashes)} for key,method,function in METHODS}
    report={'format':'c245532-separator-analysis-v1','case_id':cfg['case_id'],
        'analysis_complete':True,'measurements':measurements,
        'source_hashes':hashes,'provenance':provenance,
        'legal_verdict_claimed':False,'physical_acceptance_claimed':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
