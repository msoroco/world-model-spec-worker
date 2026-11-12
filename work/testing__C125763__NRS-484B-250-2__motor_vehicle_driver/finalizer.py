"""Saved-only C125763 yield-sign crossing analysis from original Native sources."""
import argparse
import hashlib
import json
from pathlib import Path

from capture_sources import CAMERAS
from runner import ASSIGNMENT, CASE_IDS
from simultaneous_entries import analyze


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _controls(attempt,samples,relation):
    controls=_rows(attempt/'controller_history.jsonl')
    if len(controls)!=len(samples):
        raise ValueError('Controller history does not cover every original frame')
    holds=[];slowdowns=[]
    for row,sample in zip(controls,samples):
        if row.get('frame')!=sample['frame'] or row.get('time_s')!=sample['time_s']:
            raise ValueError('Controller history original-frame join failed')
        if (type(row.get('ego_yield_control_active')) is not bool or
                type(row.get('other_conflict_clear')) is not bool or
                row['ego_yield_control_active'] is row['other_conflict_clear']):
            raise ValueError('Original yield controller readback missing')
        if relation=='opposite_directions' and row.get('other_left_turn_intended') is not True:
            raise ValueError('Original opposite left-turn controller intention missing')
        ego=row.get('commands',{}).get('ego',{})
        if not all(type(ego.get(key)) in (int,float) for key in ('throttle','brake','speed_mps')):
            raise ValueError('Original ego control values missing')
        if ego['speed_mps']<2.0 and row['ego_yield_control_active']:
            slowdowns.append(row['frame'])
        if ego['brake']>0 and not row['other_conflict_clear']:
            holds.append(row['frame'])
    return {'recorded_yield_slowdown_frames':slowdowns,
            'recorded_conflict_hold_frames':holds,
            'controller_sample_count':len(controls),
            'legal_yield_judgment':'unresolved'}


def source_crossing_identity(context):
    return {key:context[key] for key in ('native_map_id','intersection_id',
        'ego_highway_id','other_highway_id','same_statutory_crossing')}


def complete_body_first_entry(report):
    return {'first_body_entry':report['first_body_entry'],
            'absolute_difference_s':report['absolute_entry_time_difference_s'],
            'approximately_same_time_judgment':'unresolved'}


def original_approach_cross_product(report,relation):
    return {'other_spatially_right':report['other_spatially_right_of_ego_approach'],
            'inapplicable_to_opposite_exception':relation=='opposite_directions',
            'signed_lateral_offset_m':report['other_right_signed_cross_m']}


def native_yield_sign_identity(context):
    return {'native_yield_sign_id':context['native_yield_sign_id'],
            'official_device_judgment':'unresolved',
            'governance_judgment':'unresolved',
            'subsection_4_judgment':'unresolved'}


def original_approach_and_controller_intention(relation):
    return {'opposite_approach':relation=='opposite_directions',
            'exception_judgment':'unresolved'}


def original_yield_slowdown_and_conflict_hold(control):
    return control


def finalize(attempt,output):
    from worker_exchange.native_output import physical_result,write_result

    attempt=Path(attempt);output=Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Use a fresh attempt and output; retain original finalization')
    required=('config.json','junction_context.json','crossing_history.jsonl',
              'controller_history.jsonl','video_frames.jsonl','trace.jsonl',
              'capture/evidence.jsonl',*(name+'.mkv' for name in CAMERAS))
    for name in required:
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    case_id=config.get('selected_case_id')
    if (config.get('assignment_id')!=ASSIGNMENT or case_id not in CASE_IDS or
        config.get('law_id')!='NRS-484B-250-2' or
        config.get('cell_id')!='C125763' or
        config.get('actor')!='motor_vehicle_driver' or
        not isinstance(config.get('recording_description'),dict)):
        raise ValueError('Exact C125763 saved case configuration required')
    report=analyze(attempt)
    context=json.loads((attempt/'junction_context.json').read_text())
    if context.get('physical_acceptance_claimed') is not False:
        raise ValueError('Original context cannot claim physical acceptance')
    expected_relation=('opposite_directions' if case_id.endswith('yield_opposite_left_turn')
                       else 'different_highways')
    if report['approach_relation']!=expected_relation:
        raise ValueError('Saved approach relation differs from exact case')
    if expected_relation=='opposite_directions' and context.get('turn_intent_source')!='controller_history.jsonl':
        raise ValueError('Opposite left-turn context must cite original controller history')
    control=_controls(attempt,report['samples'],expected_relation)
    if not control['recorded_conflict_hold_frames']:
        raise ValueError('Original history does not show ego conflict response')
    if expected_relation=='different_highways':
        side=report['other_spatially_right_of_ego_approach']
        expected_side=not case_id.endswith('yield_ego_right_near_time')
        if side is not expected_side:
            raise ValueError('Original relative side differs from exact case')
    else:
        side=None
    sources={name:_sha(attempt/name) for name in required}
    measured={
      'crossing_identity':{'method':'source_crossing_identity',
        'value':source_crossing_identity(context),
        'sources':{'junction_context.json':sources['junction_context.json']}},
      'entry_timing':{'method':'complete_body_first_entry',
        'value':complete_body_first_entry(report),
        'sources':{name:sources[name] for name in
                   ('crossing_history.jsonl','video_frames.jsonl','junction_context.json')}},
      'relative_right_side':{'method':'original_approach_cross_product',
        'value':original_approach_cross_product(report,expected_relation),
        'sources':{name:sources[name] for name in
                   ('crossing_history.jsonl','junction_context.json')}},
      'device_qualification_context':{'method':'native_yield_sign_identity',
        'value':native_yield_sign_identity(context),
        'sources':{name:sources[name] for name in
                   ('junction_context.json','crossing_history.jsonl')}},
      'opposite_left_turn_context':{'method':'original_approach_and_controller_intention',
        'value':original_approach_and_controller_intention(expected_relation),
        'sources':{name:sources[name] for name in
                   ('junction_context.json','crossing_history.jsonl','controller_history.jsonl')}},
      'yield_observation':{'method':'original_yield_slowdown_and_conflict_hold',
        'value':original_yield_slowdown_and_conflict_hold(control),
        'sources':{name:sources[name] for name in
                   ('controller_history.jsonl','crossing_history.jsonl','video_frames.jsonl')}}}
    channels=attempt/'channels';channels.mkdir()
    (channels/'entry_context.json').write_text(json.dumps(
        {'entry_context':{'case_id':case_id,'measurements':measured,
                          'legal_conclusion':'unresolved'}},
        indent=2,allow_nan=False)+'\n')
    (channels/'entry_timing.jsonl').write_text(''.join(json.dumps(
        {'time_s':row['time_s'],'value':{'frame':row['frame'],
         'ego_body_in_crossing':row['ego']['body_in_crossing'],
         'other_body_in_crossing':row['other']['body_in_crossing']}},
        allow_nan=False)+'\n' for row in report['samples']))
    result={'case_id':case_id,
      'measured_values':{'absolute_entry_time_difference_s':report['absolute_entry_time_difference_s'],
                         'other_spatially_right_of_ego_approach':side},
      'target_checks':[{'target':'both_complete_bodies_enter_sourced_median_crossing',
        'requested':True,'measured':True,'method':'original complete-body polygon intersection',
        'tolerance':0,'matched':True,'physical_cause_confirmed':False,
        'cause_evidence':['junction_context.json','crossing_history.jsonl','video_frames.jsonl']}],
      'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
      'termination_reason':'Saved source analysis; independent Native and legal review pending',
      'physical_failure_flags':['official sign qualification, approximately same time and yielding remain unresolved'],
      'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':config['recording_description'],
      'recording_evidence':[{'name':'entry_context','unit':'structured record',
                              'reference':'channels/entry_context.json'},
                             {'name':'entry_timing','unit':'structured record',
                              'reference':'channels/entry_timing.jsonl'}],
      'source_evidence_hashes':sources,
      'capture_evidence_sha256':sources['capture/evidence.jsonl'],
      'realized_observables':{}}
    result=physical_result(attempt,result)
    write_result(attempt,result)
    output.write_text(json.dumps({'format':'worker-c125763-yield-sign-saved-analysis',
        'case_id':case_id,'measurements':measured,
        'physical_acceptance_claimed':False},indent=2,allow_nan=False)+'\n')
    return measured


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();measured=finalize(args.attempt,args.output)
    print(json.dumps({'measurement_keys':list(measured),'physical_acceptance_claimed':False}))

if __name__=='__main__':main()
