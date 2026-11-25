"""Finalize an original emergency-vehicle attempt from sealed saved sources."""
import argparse
import json
from pathlib import Path
import sys

if not (Path(__file__).resolve().parent / 'measure_emergency.py').is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from measure_emergency import AID, CAMERAS, measure, rows, sha

CASES=tuple(AID+'__'+suffix for suffix in
            ('controlled_1','controlled_2','official_1','official_2','preparing_movement','preparing_hand_signal'))


def statutory_branch(case_id):
    if case_id.endswith(('__official_1','__official_2')):
        return 'regulatory_moving'
    if case_id.endswith('__preparing_movement'):
        return 'emergency_preparing_movement'
    if case_id.endswith('__preparing_hand_signal'):
        return 'emergency_preparing_hand_signal'
    return 'emergency_moving'


def reviewed_authority(context, case_id):
    return (context['official_regulatory_vehicle'] if statutory_branch(case_id)=='regulatory_moving'
            else context['emergency_vehicle_authorized'])


def source_joined_same_direction_abreast_and_order(measured):
    """Return original body intervals and order without a statutory cutoff."""
    return measured['per_frame_geometry']



def validate_hand_signal_sources(source_dir, context):
    """Bind visual hand review to the same source vehicle and original frames."""
    source_dir=Path(source_dir)
    for key in ('driver_hand_signal_visual_source','driver_signal_actor_identity_source',
                'driver_signal_window_source','driver_signal_visual_review_source',
                'driver_signal_reviewer'):
        value=context.get(key)
        if not isinstance(value,str) or not value:
            raise ValueError('Original driver hand signal source missing: '+key)
    signal_actor_id=context.get('driver_signal_actor_id')
    if type(signal_actor_id) is not int:
        raise ValueError('Original driver signal actor identity missing')
    poses=rows(source_dir/'vehicle_poses.jsonl')
    if len(poses)!=600:
        raise ValueError('Full original driver hand signal frame set required')
    for index,pose in enumerate(poses):
        source=pose.get('emergency',{})
        if source.get('driver_signal_actor_id')!=signal_actor_id:
            raise ValueError('Driver hand signal actor source join differs')
        visible=source.get('driver_hand_signal_visible')
        if type(visible) is not bool or visible!=(80<=index<120):
            raise ValueError('Driver hand signal phase evidence differs')
        if 80<=index<120 and source.get('speed_mps',1)>0.05:
            raise ValueError('Hand signal preparation must be distinct from vehicle movement')
    if context.get('review_kind')=='original_source_review':
        if context.get('driver_signal_pixels_reviewed') is not True:
            raise ValueError('Original driver hand signal pixels unreviewed')
        if context.get('driver_identity_reviewed') is not True:
            raise ValueError('Original driver identity unreviewed')

def finalize(source_dir, case_id, output, *, diagnostic=False):
    if case_id not in CASES:
        raise ValueError('Exact emergency or regulatory case required')
    source_dir=Path(source_dir)
    ctx=json.loads((source_dir/'emergency_context.json').read_text())
    expected='synthetic_diagnostic' if diagnostic else 'original_source_review'
    if ctx.get('review_kind')!=expected or ctx.get('case_id')!=case_id:
        raise ValueError('Exact case and source review provenance required')
    if case_id.endswith('__preparing_hand_signal'):
        validate_hand_signal_sources(source_dir,ctx)
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
    if case_id.endswith('__preparing_hand_signal'):
        validate_hand_signal_sources(attempt,context)
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
    context_name=('regulatory_vehicle_context' if statutory_branch(case_id)=='regulatory_moving'
                  else 'emergency_context')
    review_context={context_name:{
        'authorized':reviewed_authority(context,case_id),
        'qualifying_flash_equipment_reviewed':context['qualifying_flash_equipment_reviewed'],
        'source_review_kind':context['review_kind'],
        'source_sha256':sha(attempt/'emergency_context.json')},
        'officer_direction_context':context['officer_directed_otherwise']}
    if statutory_branch(case_id) in ('emergency_preparing_movement','emergency_preparing_hand_signal'):
        review_context['preparing_to_move_context']={
            'reviewed':context['preparing_to_move_reviewed'],
            'preparing_to_move_source':context['preparing_to_move_source'],
            'visible_preparation_mode_source':context['visible_vehicle_movement_source' if statutory_branch(case_id)=='emergency_preparing_movement' else 'driver_hand_signal_visual_source'],
            'visible_preparation_frames':measured['visible_preparation_frames'],
            'source_sha256':sha(attempt/'emergency_context.json')}
    (channels/'context-review.json').write_text(json.dumps(review_context,indent=2,allow_nan=False)+'\n')
    for descriptor in construction['recording_description']['context_inputs']:
        evidence.append({'name':descriptor['name'],'unit':descriptor['unit'],
                         'reference':'channels/context-review.json'})
    requested=case_id.endswith(('__controlled_2','__official_2'))
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
            'statutory_branch':statutory_branch(case_id),
            'visible_preparation_frames':measured['visible_preparation_frames'],
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
