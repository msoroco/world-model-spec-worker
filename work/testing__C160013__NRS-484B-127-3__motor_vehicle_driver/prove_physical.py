"""CPU-only complete, incomplete and missing-source group motion fixtures."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from motorcade_spacing import CASES, measure_original_frames
from runner import AID

ROOT = Path(__file__).resolve().parent


def prove(case_id, kind, output, scratch_root):
    matches = [case for case in CASES if case_id == AID + '__' + case.suffix]
    if len(matches) != 1 or kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('exact physical fixture case/kind required')
    case = matches[0]
    source = ROOT/'diagnostics'/case.suffix
    shared = ROOT/'diagnostics/_shared'
    construction = json.loads((ROOT/'cases'/case.suffix/'construction.json').read_text())
    config = json.loads(next(file['content'] for file in construction['files'] if file['path']=='config.json'))
    scratch_root = Path(scratch_root)
    scratch_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root,prefix='physical-fixture-') as temporary:
        attempt = Path(temporary)
        (attempt/'config.json').write_text(json.dumps(config)+'\n')
        for name in ('video_frames.jsonl','trace.jsonl'):
            shutil.copyfile(shared/name,attempt/name)
        shutil.copyfile(source/'caravan_history.jsonl',attempt/'caravan_history.jsonl')
        if kind != 'missing_evidence':
            shutil.copyfile(source/'caravan_context.json',attempt/'caravan_context.json')
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (attempt/'caravan_history.jsonl').read_text().splitlines()]
            for row in rows:
                row['participants']['entrant']['lane_id'] = -2
            (attempt/'caravan_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        history = [json.loads(line) for line in (source/'original-group-history.jsonl').read_text().splitlines()]
        measured = measure_original_frames(history,case)
        checks = [
            {'target':name,'requested':case.gap_target_m,'measured':value,
             'method':'synthetic original-frame body interval diagnostic',
             'tolerance':3.0,'matched':abs(value-case.gap_target_m)<3,
             'physical_cause_confirmed':False,
             'cause_evidence':{'original-group-history.jsonl':'synthetic fixture source'}}
            for name,value in (('front group gap',measured['steady_front_mean_m']),
                               ('rear group gap',measured['steady_rear_mean_m']))
        ]
        from worker_exchange.native_output import physical_result
        result = {
            'case_id':case_id,'measured_values':{'steady_front_mean_m':measured['steady_front_mean_m'],
                                               'steady_rear_mean_m':measured['steady_rear_mean_m']},
            'target_checks':checks,'setup_confirmed':False,'behavior_attempted':False,
            'maneuver_completed':False,'termination_reason':'synthetic CPU motion fixture',
            'physical_failure_flags':[],'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['case']['recording_description'],
            'recording_evidence':[],'realized_observables':{},
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
        }
        result = physical_result(attempt,result)
        expected={'complete_motion':'met','incomplete_motion':'not_met',
                  'missing_evidence':'unverified'}[kind]
        actual=result['physical_checks']['maneuver']['status']
        if actual!=expected:
            raise ValueError('physical fixture status '+actual+' differs from '+expected+
                             ': '+str(result['physical_checks']['maneuver'].get('details')))
        output=Path(output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(case.suffix,kind,actual)


def verify_lifecycle():
    """CPU state-machine proof of the required ownership closure order."""
    events = ['capture_finished','encoders_closed','restoration_verified',
              'native_exit','owner_released','saved_processing_started']
    def transition(observed):
        if observed != events[:len(observed)]:
            raise ValueError('saved processing before Native ownership closure')
        return observed
    for length in range(1,len(events)+1):
        transition(events[:length])
    try:
        transition(events[:4]+['saved_processing_started'])
    except ValueError as error:
        print(str(error))
    else:
        raise AssertionError('early saved processing accepted')
    print(','.join(events))
    return events


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind')
    parser.add_argument('--output')
    parser.add_argument('--scratch-root')
    parser.add_argument('--lifecycle',action='store_true')
    args=parser.parse_args()
    if args.lifecycle:
        verify_lifecycle()
    else:
        if not all((args.case,args.kind,args.output,args.scratch_root)):
            raise ValueError('case, kind, output and scratch root required')
        prove(args.case,args.kind,args.output,args.scratch_root)
