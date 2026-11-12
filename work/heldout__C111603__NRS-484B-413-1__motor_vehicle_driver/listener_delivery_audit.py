"""Independent exact listener attempt audit; physical judgments remain open."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from turn_signal_measurement import measure

SOURCES=('ego_turn_motion.jsonl','ego_signal_audio.jsonl','affected_participants.json',
         'participant_bodies.jsonl','listener_audio_original.jsonl','horn_actuation.jsonl')
VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def sha(path): return sha256(Path(path).read_bytes()).hexdigest()


def rows(path): return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def require(condition,message):
    if not condition: raise ValueError(message)


def audit(case,attempt,negative=False):
    require(case.startswith(HERE.name+'__ped_horn_listener_') and case.endswith('m'),
            'Wrong exact listener case')
    offset=int(case.rsplit('_',1)[-1][:-1])
    require(offset in (2,4,6),'Unknown listener distance point')
    attempt=Path(attempt)
    report=json.loads((attempt/'analysis-report.json').read_text())
    require(report['case_id']==case and not report.get('physical_acceptance_claimed') and
            not report.get('legal_acceptance_claimed'),'Wrong listener report')
    observation=report['measurements']['turn_signal_observation']
    names=(*SOURCES,'video_frames.jsonl','trace.jsonl',*VIDEOS)
    hashes={name:sha(attempt/name) for name in names}
    if negative: observation['sources']['participant_bodies.jsonl']='0'*64
    require(observation['sources']==hashes,'Stale or missing original listener body source')
    value=measure(*(attempt/name for name in SOURCES[:4]))
    require(value==observation['value'] and value['pedestrian_may_be_affected'] and
            not value['vehicle_may_be_affected'],'Listener source measurement differs')
    require(value['clearly_audible_legal_judgment'] is None and
            value['max_pre_turn_listener_audio_rms'] is not None,
            'Listener PCM or unresolved audibility differs')
    motion=rows(attempt/'ego_turn_motion.jsonl')
    bodies=rows(attempt/'participant_bodies.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    trace=rows(attempt/'trace.jsonl')
    require(len(motion)==len(bodies)==len(mapping)==len(trace)==value['frame_count'],
            'Listener original frame inventory differs')
    gaps=[]
    for index,(ego,body,mapped,point) in enumerate(zip(motion,bodies,mapping,trace)):
        require(ego['frame']==body['frame']==point['frame']==mapped['carla_frame'] and
                mapped['video_frame']==index and mapped['time_s']==point['time_s'],
                'Listener original frame join differs')
        listener=body['bodies']['ped_listener']
        gap=math.hypot(ego['x_m']-listener['x_m'],ego['y_m']-listener['y_m'])
        gap-=ego['body_radius_m']+listener['body_radius_m']
        require(math.isfinite(gap),'Nonfinite original listener gap')
        gaps.append(gap)
    context=json.loads((attempt/'affected_participants.json').read_text())
    require(context['participant_types']['ped_listener']=='pedestrian' and
            context.get('listener_position_source') and context.get('participant_geometry_source'),
            'Original listener placement provenance differs')
    provenance=attempt/'turn_fixture_provenance.json'
    if provenance.exists():
        require(json.loads(provenance.read_text())['case_id']==case,
                'Diagnostic listener provenance differs')
    else:
        require(context.get('listener_requested_route_offset_m')==offset,
                'Native route-relative listener offset missing')
    for name in VIDEOS:
        audit_video(attempt/name,len(mapping),mapping_sha256=hashes['video_frames.jsonl'])
    return {'format':'worker-listener-exact-delivery-audit','case_id':case,
            'source_integrity_passed':True,'joined_frames':len(mapping),'video_decode_count':4,
            'minimum_sampled_ped_gap_m':min(gaps),'requested_offset_m':offset,
            'physical_audibility_verified':False,'affected_party_judgment_verified':False,
            'legal_acceptance_claimed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--negative',action='store_true')
    args=p.parse_args()
    result=audit(args.case,args.attempt,args.negative)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(args.case,'independent_listener_delivery_audit_passed')
