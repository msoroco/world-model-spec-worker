"""Finalize an original emergency-vehicle attempt from sealed saved sources."""
import argparse
import json
from pathlib import Path

from measure_emergency import AID, CAMERAS, measure, rows, sha

CASES=tuple(AID+'__'+suffix for suffix in
            ('controlled_1','controlled_2','official_1','official_2'))


def statutory_branch(case_id):
    return 'regulatory_moving' if case_id.endswith(('__official_1','__official_2')) else 'emergency_moving'


def reviewed_authority(context, case_id):
    return (context['official_regulatory_vehicle'] if statutory_branch(case_id)=='regulatory_moving'
            else context['emergency_vehicle_authorized'])


def source_joined_same_direction_abreast_and_order(measured):
    """Return original body intervals and order without a statutory cutoff."""
    return measured['per_frame_geometry']


def finalize(source_dir, case_id, output, *, diagnostic=False):
    if case_id not in CASES:
        raise ValueError('Exact emergency or regulatory case required')
    source_dir=Path(source_dir)
    ctx=json.loads((source_dir/'emergency_context.json').read_text())
    expected='synthetic_diagnostic' if diagnostic else 'original_source_review'
    if ctx.get('review_kind')!=expected or ctx.get('case_id')!=case_id:
        raise ValueError('Exact case and source review provenance required')
    measured=measure(source_dir,branch=statutory_branch(case_id))
    measured['case_id']=case_id
    measured['source_review_kind']=expected
    measured['selected_outcome_observed']=None
    measured['physical_acceptance_claimed']=False
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Saved report already exists')
    output.write_text(json.dumps(measured,indent=2,sort_keys=True)+'\n')
    return {'case_id':case_id,'samples':measured['samples'],
            'source_review_kind':expected,'physical_acceptance_claimed':False}


def finalize_attempt(attempt, output):
    """Build canonical saved channels and result from unchanged source records."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    for name in ('config.json','construction.json','emergency_context.json',
                 'vehicle_poses.jsonl','video_frames.jsonl','trace.jsonl',
                 *(name+'.mkv' for name in CAMERAS)):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    cfg=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    context=json.loads((attempt/'emergency_context.json').read_text())
    case_id=cfg.get('case_id')
    if (case_id not in CASES or
            construction.get('case_id')!=case_id or context.get('case_id')!=case_id):
        raise ValueError('Exact saved case identity differs')
    measured=measure(attempt,branch=statutory_branch(case_id))
    mapping=rows(attempt/'video_frames.jsonl')
    poses=rows(attempt/'vehicle_poses.jsonl')
    channels=attempt/'channels'
    channels.mkdir()
    evidence=[]
    for descriptor in construction['recording_description']['channels']:
        name=descriptor['name']
        path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for frame,pose,geometry in zip(mapping,poses,measured['per_frame_geometry']):
                ego,emergency=pose['ego'],pose['emergency']
                values={
                    'drv.responding_emergency':{'actor_id':emergency['actor_id'],
                        'authorized_review':reviewed_authority(context,case_id),
                        'qualifying_equipment_review':context['qualifying_flash_equipment_reviewed'],
                        'flashing_light_phase_on':emergency['flashing_light_phase_on']},
                    'rel.same_direction':{'heading_dot':geometry['heading_dot'],
                        'ego_heading_rad':ego['heading_rad'],
                        'emergency_heading_rad':emergency['heading_rad']},
                    'rel.longitudinal_overlap':geometry['longitudinal_overlap_length_m'],
                    'drv.overtaking':geometry['ego_minus_emergency_longitudinal_m'],
                    'rel.ahead_behind_in_lane':{'longitudinal_m':geometry['ego_minus_emergency_longitudinal_m'],
                        'lateral_m':geometry['lateral_separation_m']},
                    'kin.velocity':{'ego_mps':ego['speed_mps'],
                        'emergency_mps':emergency['speed_mps']},
                    'dev.human_direction':context['officer_directed_otherwise'],
                }
                if name not in values:
                    raise ValueError('Unknown declared recording channel: '+name)
                stream.write(json.dumps({'time_s':frame['time_s'],'value':values[name]},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':descriptor['unit'],'reference':'channels/'+path.name})
    review_context={'emergency_context':{
        'authorized':reviewed_authority(context,case_id),
        'qualifying_flash_equipment_reviewed':context['qualifying_flash_equipment_reviewed'],
        'source_review_kind':context['review_kind'],
        'source_sha256':sha(attempt/'emergency_context.json')},
        'officer_direction_context':context['officer_directed_otherwise']}
    (channels/'context-review.json').write_text(json.dumps(review_context,indent=2,allow_nan=False)+'\n')
    for descriptor in construction['recording_description']['context_inputs']:
        evidence.append({'name':descriptor['name'],'unit':descriptor['unit'],
                         'reference':'channels/context-review.json'})
    requested=case_id.endswith('__controlled_2')
    observed=any(row['longitudinal_overlap_length_m']>0 for row in measured['per_frame_geometry'])
    result={'case_id':case_id,'measured_values':{
                'overlap_frames':sum(row['longitudinal_overlap_length_m']>0 for row in measured['per_frame_geometry']),
                'relative_order_crossings':measured['relative_order_crossings'],
                'source_sha256':measured['source_sha256']},
            'target_checks':[{'target':'same-direction body overlap during original 600-frame window',
                'requested':requested,'measured':observed,
                'method':'source-joined original body intervals; no legal cutoff',
                'tolerance':0,'matched':requested==observed,
                'physical_cause_confirmed':False,
                'cause_evidence':['vehicle_poses.jsonl','video_frames.jsonl','emergency_context.json']}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'full 600-frame saved observation window',
            'physical_failure_flags':['Original physical camera coverage and legal qualification unverified'],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':construction['recording_description'],
            'recording_evidence':evidence,'realized_observables':{},
            'provenance_kind':'original_native' if context['review_kind']=='original_source_review'
                              else 'synthetic_local_diagnostic','accepted':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    measurement_sources=('video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl',
                         'emergency_context.json',*(name+'.mkv' for name in CAMERAS))
    report={'format':'source-bound-emergency-finalization-v1','case_id':case_id,
            'measurements':{'per_frame_geometry':{'method':'source_joined_same_direction_abreast_and_order',
                'value':source_joined_same_direction_abreast_and_order(measured),
                'sources':{name:sha(attempt/name) for name in measurement_sources}}},
            'relative_order_crossings':measured['relative_order_crossings'],
            'source_review_kind':context['review_kind'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path)
    parser.add_argument('--source-dir',type=Path)
    parser.add_argument('--case')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--diagnostic',action='store_true')
    args=parser.parse_args()
    if args.attempt:
        print(json.dumps(finalize_attempt(args.attempt,args.output),sort_keys=True))
    else:
        if not args.source_dir or not args.case:
            parser.error('--source-dir and --case are required without --attempt')
        print(json.dumps(finalize(args.source_dir,args.case,args.output,diagnostic=args.diagnostic),sort_keys=True))
