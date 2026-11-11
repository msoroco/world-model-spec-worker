"""Saved-only following analysis from retained Native acquisition sources."""
import argparse
import hashlib
import json
from pathlib import Path
from following_measurements import analyze

CAMERAS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def measure_minimum_following_gap(report):
    return report["minimum_sampled_body_gap_m"]

def measure_following_context(report):
    return {"samples":[{"frame":row["frame"],"ego_speed_mps":row["ego_speed_mps"],
             "lead_speed_mps":row["lead_speed_mps"],"lead_brake":row["lead_brake"],
             "surface_condition":row["surface_condition"],"traffic_actor_ids":row["traffic_actor_ids"]}
            for row in report["samples"] if row["following"]]}

def measure_following_interval(report):
    return report["following_end"]["time_s"]<report["first_lane_change"]["time_s"]

def finalize(attempt:Path,output:Path)->dict:
    from worker_exchange.native_output import write_result
    attempt,output=Path(attempt),Path(output)
    required=('config.json','road_context.json','vehicle_history.jsonl',
              'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl',*CAMERAS)
    for name in required:
        if not (attempt/name).is_file():raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    case_id=config.get('selected_case_id')
    if not case_id or not config.get('recording_description'):
        raise ValueError('Exact case and recording description required')
    target=config.get('requested_engineering_gap_m')
    tolerance=config.get('engineering_gap_tolerance_m',1.0)
    if type(target) not in (int,float) or target<=0 or type(tolerance) not in (int,float) or tolerance<=0:
        raise ValueError('Finite positive engineering gap target/tolerance required')
    report=analyze(attempt)
    gap=measure_minimum_following_gap(report)
    following_context=measure_following_context(report)
    ends_before_change=measure_following_interval(report)
    source_hashes=report['sources']
    result={'case_id':case_id,
            'measured_values':{'minimum_sampled_body_gap_m':gap,
                               'following_end_before_lane_change':ends_before_change},
            'target_checks':[{'target':'minimum_sampled_body_gap_m','requested':target,'measured':gap,
                              'method':'original complete-body longitudinal projections along sourced following lane',
                              'tolerance':tolerance,'matched':abs(gap-target)<=tolerance,
                              'physical_cause_confirmed':False,
                              'cause_evidence':['vehicle_history.jsonl','video_frames.jsonl']}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'saved original-source analysis; physical completion requires independent audit',
            'physical_failure_flags':['reasonable-and-prudent legal judgment unresolved','physical visibility unverified'],
            'trace_reference':'trace.jsonl','video_references':list(CAMERAS),
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':{'source_hashes':source_hashes,
                                  'capture_evidence_sha256':sha(attempt/'capture/evidence.jsonl')},
            'realized_observables':{'following_start':report['following_start'],
                                    'following_end':report['following_end'],
                                    'first_lane_change':report['first_lane_change'],
                                    'minimum_sampled_body_gap_m':gap,
                                    'reasonable_and_prudent_judgment':'unresolved'}}
    analysis={'format':'worker-following-analysis','case_id':case_id,
              'measurements':{'minimum_sampled_body_gap_m':{'method':'measure_minimum_following_gap',
                  'value':gap,'sources':source_hashes},
                  'following_context':{'method':'measure_following_context',
                  'value':following_context,'sources':source_hashes},
                  'following_end_before_lane_change':{'method':'measure_following_interval',
                  'value':result['measured_values']['following_end_before_lane_change'],
                  'sources':source_hashes}},
              'source_report':report}
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    write_result(attempt,result)
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
    return analysis

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(Path(args.attempt),Path(args.output))
if __name__=='__main__':main()
