"""Independent source-bound C10808 delivery audit; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

PREFIX='testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__'
VIDEOS=('overview.mkv','approach.mkv','reference_corner.mkv',
        'driver_reference.mkv')
ORIGINAL=('phase-events.jsonl','pedestrian-context.jsonl','sign-inventory.json',
          'sign-authorization-source','trace.jsonl','video_frames.jsonl',
          'road.xodr',*VIDEOS)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def within(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
        raise ValueError('original source missing or outside attempt: '+str(name))
    return path


def center(vertices):
    if (not isinstance(vertices,list) or len(vertices)<4 or any(
            not isinstance(point,list) or len(point)<2 or
            any(type(value) not in (int,float) or not math.isfinite(value)
                for value in point[:2]) for point in vertices)):
        raise ValueError('original body geometry incomplete')
    return [(min(p[i] for p in vertices)+max(p[i] for p in vertices))/2
            for i in (0,1)]


def audit(attempt,processing,decode_receipt,case_id,media_verify=None):
    attempt=Path(attempt).resolve()
    if not case_id.startswith(PREFIX):raise ValueError('unknown exact C10808 case')
    provenance=read(attempt/'acquisition-provenance.json')
    if ((attempt/'fixture-provenance.json').exists() or
            provenance.get('provenance_kind')!='native' or
            provenance.get('diagnostic_fixture') is not False):
        raise ValueError('diagnostic fixture cannot establish Native delivery')
    seal=read(attempt/'capture-seal.json')
    if (seal.get('provenance_kind')!='native' or
            seal.get('events')!=['capture_finished','encoders_closed',
                            'restoration_verified'] or
            seal.get('restoration',{}).get('restored') is not True):
        raise ValueError('Native capture lifecycle incomplete')
    if not set(ORIGINAL)<=set(seal.get('sources',{})):
        raise ValueError('Native seal omits original C10808 source')
    for name,digest in seal['sources'].items():
        if sha(within(attempt,name))!=digest:
            raise ValueError('sealed original missing or changed: '+name)
    native_exit=read(attempt/'native-exit.json')
    if (native_exit.get('event')!='native_exit' or
            native_exit.get('capture_seal_sha256')!=sha(attempt/'capture-seal.json')):
        raise ValueError('Native exit does not bind capture seal')
    owner=read(attempt/'owner-release.json')
    if (owner.get('event')!='owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json')):
        raise ValueError('owner release missing or stale')
    acquisition=read(attempt/'acquisition.json')
    for name in ORIGINAL:
        item=acquisition.get(name,{})
        if item.get('kind')!='original_native' or item.get('sha256')!=sha(attempt/name):
            raise ValueError('original acquisition missing or changed: '+name)
    sign=read(attempt/'sign-inventory.json')
    if (sign.get('message')!='NO U TURN' or not sign.get('erected') or
            sign.get('authorization_source_sha256')!=sha(attempt/'sign-authorization-source')):
        raise ValueError('sign identity or authorization-source binding missing')
    events=rows(attempt/'phase-events.jsonl')
    contexts=rows(attempt/'pedestrian-context.jsonl')
    trace=rows(attempt/'trace.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if not events or not len(events)==len(contexts)==len(trace)==len(mapping):
        raise ValueError('original event/trace/video frame coverage incomplete')
    ids={(row.get('operator_id'),row.get('bicycle_id'),row.get('sign_id'))
         for row in events}
    if (len(ids)!=1 or None in next(iter(ids)) or
            sign.get('sign_actor_id')!=next(iter(ids))[2]):
        raise ValueError('original sign/operator/bicycle continuity changed')
    separations=[];phases=[]
    for index,(event,context,motion,frame) in enumerate(zip(events,contexts,trace,mapping)):
        if (frame.get('video_frame')!=index or
                any(row.get('frame')!=frame.get('carla_frame') or
                    abs(row.get('time_s',float('inf'))-frame.get('time_s',0))>1e-4
                    for row in (event,motion))):
            raise ValueError('original event/trace/camera frame join changed')
        if index and frame['time_s']<=mapping[index-1]['time_s']:
            raise ValueError('original frame time order changed')
        if (context.get('frame')!=event['frame'] or
                abs(context.get('time_s',float('inf'))-event['time_s'])>1e-4 or
                context.get('operator_id')!=event['operator_id'] or
                context.get('pedestrian_regulation_assessment')!='unresolved' or
                not isinstance(context.get('nearby_crosswalk_vertices_m'),list) or
                not isinstance(context.get('nearby_control_devices'),list)):
            raise ValueError('original pedestrian context source join changed')
        separation=math.dist(center(event.get('operator_body_vertices_m')),
                             center(event.get('bicycle_body_vertices_m')))
        separations.append(separation);phases.append(event.get('phase'))
    if phases[0]!='mounted_approach' or phases[-1]!='turn_complete':
        raise ValueError('approach or U-turn completion phase absent')
    dismounted=case_id.endswith('__dismount_before_uturn')
    if dismounted:
        if ('dismount_hold' not in phases or 'afoot_reversal' not in phases or
                'mounted_reversal' in phases or
                phases.index('dismount_hold')>=phases.index('afoot_reversal') or
                any(distance<1.0 for phase,distance in zip(phases,separations)
                    if phase in ('afoot_reversal','turn_complete'))):
            raise ValueError('original dismount before reversal not demonstrated')
    elif ('mounted_reversal' not in phases or 'afoot_reversal' in phases or
          'dismount_hold' in phases or any(distance>.5 for distance in separations)):
        raise ValueError('original mounted reversal not demonstrated')
    saved=read(processing)
    if (saved.get('format')!='worker-saved-processing' or
            saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id')!=case_id):
        raise ValueError('saved-only processing receipt missing or failed')
    result_path=Path(saved.get('result',''))
    if not result_path.is_file() or saved.get('result_sha256')!=sha(result_path):
        raise ValueError('saved Native result missing or changed')
    result=read(result_path)
    if (result.get('case_id')!=case_id or
            not all(result.get(key) is True for key in
                    ('setup_confirmed','behavior_attempted','maneuver_completed')) or
            result.get('diagnostic_fixture') is True):
        raise ValueError('exact physical completion remains unconfirmed')
    video=Path(saved.get('analysis_directory',''))/'raw.mkv'
    if not video.is_file() or not Path(decode_receipt).is_file():
        raise ValueError('decoded primary video or receipt missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        checker=sha(Path(__file__).with_name('pixel_checks.py'))
        def media_verify(video,receipt,count,mapping_sha256):
            return verify_receipt(video,receipt,count,
                mapping_sha256=mapping_sha256,
                required_checks={'c10808_four_view_pixels':checker})
    media_verify(video,decode_receipt,len(mapping),
                 mapping_sha256=sha(attempt/'video_frames.jsonl'))
    config=read(attempt/'config.json')
    if config.get('selected_case_id')!=case_id:
        raise ValueError('original configuration selects another case')
    return {'format':'worker-delivery-audit','passed':True,'case_id':case_id,
            'law_id':config['law_id'],'cell_id':config['cell_id'],
            'actor_id':config['actor'],'frame_count':len(mapping),
            'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'native_result_sha256':sha(result_path),
            'source_decode_receipt_sha256':sha(decode_receipt),
            'sign_source_sha256':sha(attempt/'sign-authorization-source'),
            'dismounted_before_turn':dismounted,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser()
    for key in ('attempt','processing','decode-receipt','case'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt,
                           args.case),indent=2))


if __name__=='__main__':main()
