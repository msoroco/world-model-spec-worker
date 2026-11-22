"""Independent source and physical audit for one straight-arrow Native delivery."""
import argparse
import hashlib
import json
from pathlib import Path

from arrow_source import load_binding
from phase_source import entry_observation, load as load_phase_source


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_arrow_source(attempt,acquisition,seal,signals,context):
    """Independently join reviewed asset, installation and every green frame."""
    provenance_path=attempt/'acquisition-provenance.json'
    if not provenance_path.is_file() or 'acquisition-provenance.json' not in seal['sources']:
        raise ValueError('reviewed arrow acquisition provenance absent')
    names=read(provenance_path).get('reviewed_arrow_sources')
    if not isinstance(names,list) or not names or len(names)%2:
        raise ValueError('reviewed arrow packet/asset pair absent')
    bindings=[]
    for packet_name,asset_name in zip(names[::2],names[1::2]):
        if not all(isinstance(name,str) and name.startswith('reviewed-arrow-sources/') and
                   Path(name).as_posix()==name and '..' not in Path(name).parts
                   for name in (packet_name,asset_name)):
            raise ValueError('invalid reviewed arrow source path')
        for name in (packet_name,asset_name):
            if name not in seal['sources'] or acquisition.get(name,{}).get('sha256')!=sha(attempt/name):
                raise ValueError('reviewed arrow source unsealed or stale')
        bindings.append(load_binding(attempt/packet_name,attempt/asset_name))
    chosen=[binding for binding in bindings if binding['packet']['actor_id']==context['facing_head_id']]
    if len(chosen)!=1:raise ValueError('facing arrow lacks unique reviewed actor')
    binding=chosen[0];packet=binding['packet']
    if context.get('arrow_review_packet_sha256')!=binding['packet_sha256'] or \
       context.get('arrow_review_asset_sha256')!=binding['asset_sha256']:
        raise ValueError('intersection context differs from reviewed arrow source')
    for index,signal in enumerate(signals):
        aspect=signal.get('aspect',{})
        candidate=[item for item in signal.get('candidate_lights',[])
                   if item.get('actor_id')==packet['actor_id']]
        if len(candidate)!=1:raise ValueError('reviewed arrow actor missing from original frame')
        observed=candidate[0]
        if observed.get('blueprint_id')!=packet['blueprint_id'] or \
           any(abs(a-b)>.25 for a,b in zip(observed.get('position_m',[]),packet['position_m'])) or \
           len(observed.get('position_m',[]))!=3 or \
           abs(((observed.get('yaw_deg',999)-packet['yaw_deg']+180)%360)-180)>2:
            raise ValueError('reviewed arrow installation differs from original frame')
        green=str(observed.get('state')).split('.')[-1]=='Green'
        if signal.get('authored_state') is not None:
            from runner import authored_arrow_state,load_scene
            schedule=authored_arrow_state(load_scene(),index/20)
            if signal['authored_state']!=schedule or str(observed.get('state')).split('.')[-1]!=schedule:
                raise ValueError('original arrow state differs from predeclared schedule')
        if aspect.get('packet_sha256')!=binding['packet_sha256'] or \
           aspect.get('asset_sha256')!=binding['asset_sha256'] or \
           aspect.get('source_ref')!='reviewed-asset-sha256:'+binding['asset_sha256']+';packet-sha256:'+binding['packet_sha256'] or \
           aspect.get('head_id')!=packet['actor_id'] or \
           aspect.get('observed_frame')!=signal.get('frame') or \
           aspect.get('source_verified') is not green or \
           aspect.get('illuminated_indications')!=(packet['green_indications'] if green else []):
            raise ValueError('per-frame arrow claim differs from reviewed source and live actor')


def audit_phase_sources(attempt,acquisition,seal,signals,traffic,context):
    """Recompute retained participant entry claims from original phase frames."""
    from runner import overlaps
    provenance=read(attempt/'acquisition-provenance.json')
    names=provenance.get('reviewed_phase_sources',[])
    if not isinstance(names,list) or len(names)%2:
        raise ValueError('reviewed participant phase source inventory invalid')
    receipt_path=attempt/'participant-phase-bindings.json'
    binding_rows=[]
    if receipt_path.is_file():
        name='participant-phase-bindings.json'
        if name not in seal['sources'] or acquisition.get(name,{}).get('sha256')!=sha(receipt_path):
            raise ValueError('participant phase binding receipt unsealed or stale')
        binding_rows=read(receipt_path)
        if not isinstance(binding_rows,list):raise ValueError('participant phase binding receipt invalid')
    bindings={}
    for packet_name,source_name in zip(names[::2],names[1::2]):
        if not all(isinstance(name,str) and name.startswith('reviewed-phase-sources/') and
                   Path(name).as_posix()==name and '..' not in Path(name).parts
                   for name in (packet_name,source_name)):
            raise ValueError('reviewed participant phase source path invalid')
        for name in (packet_name,source_name):
            if name not in seal['sources'] or acquisition.get(name,{}).get('sha256')!=sha(attempt/name):
                raise ValueError('reviewed participant phase source unsealed or stale')
        binding=load_phase_source(attempt/packet_name,attempt/source_name)
        packet=binding['packet']
        if packet.get('participant_slot') is None:
            ident=packet['participant_actor_id']
        else:
            matches=[row for row in binding_rows if row.get('packet_sha256')==binding['packet_sha256']]
            if len(matches)!=1:raise ValueError('reviewed participant slot lacks unique Native binding')
            row=matches[0]
            if row.get('participant_slot')!=packet['participant_slot'] or \
               row.get('participant_role')!=packet['participant_role'] or \
               row.get('participant_blueprint_id')!=packet['participant_blueprint_id'] or \
               type(row.get('participant_actor_id')) is not int:
                raise ValueError('reviewed participant slot binding differs from source')
            ident=row['participant_actor_id']
            binding={**binding,'bound_actor_id':ident}
        if ident in bindings:raise ValueError('duplicate reviewed participant phase actor')
        bindings[ident]=binding
    regions=[context['intersection_bounds_m'],*context['adjacent_crosswalk_bounds_m']]
    previous={};entry_status={}
    for signal,row in zip(signals,traffic):
        current={}
        for person in row['participants']:
            ident=person['id']
            inside=any(overlaps(person['body_vertices_m'],region) for region in regions)
            current[ident]=inside
            if not inside:
                entry_status.pop(ident,None)
                continue
            if ident not in bindings:continue
            expected_blueprint=bindings[ident]['packet'].get('participant_blueprint_id')
            if expected_blueprint is not None and person.get('blueprint_id')!=expected_blueprint:
                raise ValueError('original participant blueprint differs from reviewed source')
            observed=entry_observation(bindings[ident],person,signal['candidate_lights'],
                                       frame=signal['frame'],previous_inside=previous.get(ident),inside=inside)
            if person.get('phase_entry_observation')!=observed:
                raise ValueError('recorded participant entry differs from original phase')
            if observed['reason']=='reviewed_entry_phase':entry_status[ident]=observed
            established=entry_status.get(ident)
            expected=established['status'] if established and type(established['status']) is bool else None
            source=('reviewed-entry-phase:'+established['packet_sha256']) if expected is not None else None
            if person.get('lawfully_present') is not expected or person.get('lawful_presence_source')!=source:
                raise ValueError('participant lawful-presence claim differs from reviewed entry source')
        for ident in tuple(entry_status):
            if ident not in current:entry_status.pop(ident,None)
        previous=current
    return len(bindings)


def audit(attempt,processing,decode_receipt,case_id,media_verify=None):
    attempt=Path(attempt);processing=Path(processing)
    required=('signal-head-history.jsonl','ego-body-history.jsonl',
              'participant-history.jsonl','intersection-context.json',
              'trace.jsonl','video_frames.jsonl','acquisition.json','result.json',
              'controller-history.jsonl')
    seal=read(attempt/'capture-seal.json')
    if seal.get('events')!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(required)<=set(seal.get('sources',{})):
        raise ValueError('Native seal omits original straight-arrow source')
    for name,digest in seal['sources'].items():
        if not (attempt/name).is_file() or sha(attempt/name)!=digest:
            raise ValueError('sealed original missing or changed: '+name)
    exit_record=read(attempt/'native-exit.json')
    if exit_record.get('event')!='native_exit' or exit_record.get('capture_seal_sha256')!=sha(attempt/'capture-seal.json'):
        raise ValueError('Native exit does not bind seal')
    owner=read(attempt/'owner-release.json')
    if owner.get('event')!='owner_released' or owner.get('operator_attested') is not True or owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json'):
        raise ValueError('owner release missing or stale')
    original=read(attempt/'result.json')
    if original.get('case_id')!=case_id:
        raise ValueError('delivery case identity differs')
    if not all(original.get(key) is True for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('physical completion not confirmed')
    acquisition=read(attempt/'acquisition.json')
    for name in (*required[:4],'controller-history.jsonl'):
        info=acquisition.get(name,{})
        if info.get('kind')!='original_native' or info.get('sha256')!=sha(attempt/name):
            raise ValueError('original signal, body or context source absent: '+name)
    signals=rows(attempt/required[0]);ego=rows(attempt/required[1]);traffic=rows(attempt/required[2])
    trace=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    controls=rows(attempt/'controller-history.jsonl')
    if not signals or not all(len(stream)==len(mapping) for stream in (signals,ego,traffic,trace,controls)):
        raise ValueError('original frame streams incomplete')
    for index,(signal,body,participants,position,frame,control) in enumerate(zip(signals,ego,traffic,trace,mapping,controls)):
        identity=(frame.get('carla_frame'),frame.get('time_s'))
        if frame.get('video_frame')!=index or any((stream.get('frame'),stream.get('time_s'))!=identity
            for stream in (signal,body,participants,position,control)):
            raise ValueError('original frame/time join changed')
    audit_arrow_source(attempt,acquisition,seal,signals,read(attempt/'intersection-context.json'))
    phase_source_count=audit_phase_sources(attempt,acquisition,seal,signals,traffic,
                                           read(attempt/'intersection-context.json'))
    if case_id.endswith('__yield_straight') and not phase_source_count:
        raise ValueError('occupied case lacks reviewed original participant phase source')
    from runner import control_step,load_scene
    scene=load_scene();first_arrow_frame=None;exhibition_occupants=None
    for signal,body,participants,control in zip(signals,ego,traffic,controls):
        expected=control_step(scene,signal,participants['participants'],body['body_vertices_m'],
                              first_arrow_frame=first_arrow_frame,
                              exhibition_occupants=exhibition_occupants)
        first_arrow_frame=expected['first_arrow_frame']
        exhibition_occupants=expected['exhibition_occupants']
        recorded={key:value for key,value in control.items() if key not in ('frame','time_s')}
        if recorded!=expected:
            raise ValueError('recorded controller decision differs from original frame sources')
    from analysis import measure
    measured=measure(attempt)
    if measured['unverified_lawful_presence_frames']:
        raise ValueError('original participant lawful-presence source unverified')
    if measured['first_sole_arrow_frame'] is None or measured['first_ego_intersection_entry_frame'] is None:
        raise ValueError('sole arrow or straight entry unobserved')
    if measured['entry_without_verified_arrow_frames']:
        raise ValueError('intersection entry without verified sole arrow')
    if abs(measured['observed_heading_change_deg'])>15:
        raise ValueError('observed heading is not straight')
    occupied=bool(measured['lawfully_occupied_frames'])
    if case_id.endswith('__clear_straight') and occupied:
        raise ValueError('clear case contains lawful occupancy')
    if case_id.endswith('__yield_straight') and not occupied:
        raise ValueError('yield case lacks lawful occupancy')
    if measured['ego_past_stop_line_during_occupancy_frames']:
        raise ValueError('ego passed stop line before yield cleared')
    processed=read(processing)
    if processed.get('format')!='worker-saved-processing' or processed.get('passed') is not True or processed.get('recorded_only') is not True:
        raise ValueError('saved processing receipt absent or failed')
    saved_result=Path(processed.get('result',''))
    if not saved_result.is_file() or processed.get('result_sha256')!=sha(saved_result) or read(saved_result).get('case_id')!=case_id:
        raise ValueError('saved result missing, stale or wrong case')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify=verify_receipt
    video=Path(processed.get('analysis_directory',''))/'raw.mkv'
    if not video.is_file():raise ValueError('saved primary video missing')
    media_verify(video,decode_receipt,len(mapping),mapping_sha256=sha(attempt/'video_frames.jsonl'))
    return {'format':'worker-delivery-audit','passed':True,'case_id':case_id,
            'native_result_sha256':sha(attempt/'result.json'),'frame_count':len(mapping),
            'trace_sha256':sha(attempt/'trace.jsonl'),'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'video_sha256':sha(video),'source_decode_receipt_sha256':sha(decode_receipt),
            'measurement':measured,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--processing',required=True);parser.add_argument('--decode-receipt',required=True)
    parser.add_argument('--case',required=True);args=parser.parse_args()
    print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt,args.case),indent=2))


if __name__=='__main__':main()
