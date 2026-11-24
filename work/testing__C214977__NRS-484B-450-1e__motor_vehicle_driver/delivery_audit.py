"""Independent, source-bound review of a promoted C214977 delivery attempt.

Physical and pixel review packets must be supplied by a reviewer of original
evidence. Diagnostic fixtures cannot satisfy this audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit as decode, verify_receipt
from worker_exchange.native_output import validate_result


CHECKS = ('native_source','all_participants','time_join','full_video_decode',
          'actual_pixels','physical_completion')
ASSIGNMENT = 'testing__C214977__NRS-484B-450-1e__motor_vehicle_driver'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _source(root, name):
    path = (root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError('missing or unsafe original source: '+name)
    return path


def _review(packet, *, kind, case, binding):
    if (packet.get('format') != 'crosswalk-independent-'+kind+'-review'
            or packet.get('case_id') != case or packet.get('accepted') is not True
            or packet.get('source_hashes') != binding or not packet.get('reviewer')
            or not packet.get('method') or not packet.get('reviewed_frame_interval')):
        raise ValueError('independent '+kind+' review missing or stale')
    return packet


def audit(attempt, case, physical_review, pixel_review, decode_receipt,
          *, job_id, attempt_number, recording_id, auditor_path):
    root = Path(attempt).resolve()
    if not case.startswith(ASSIGNMENT+'__') or not job_id or attempt_number < 1 or not recording_id:
        raise ValueError('exact delivery identity missing')
    seal = _read(_source(root,'capture-seal.json'))
    provenance = _read(_source(root,'acquisition-provenance.json'))
    if (seal.get('format') != 'worker-sealed-capture' or seal.get('provenance_kind') != 'native'
            or seal.get('diagnostic_fixture') is not False
            or provenance.get('diagnostic_fixture') is not False
            or seal.get('restoration',{}).get('restored') is not True
            or seal.get('frames') != 900):
        raise ValueError('Native source seal or restoration incomplete')
    sources = seal.get('sources',{})
    for name, digest in sources.items():
        if _sha(_source(root,name)) != digest:
            raise ValueError('sealed original source changed: '+name)
    receipt = _read(_source(root,'native-receipt.json'))
    if receipt.get('case_id') != case or receipt.get('frame_count') != 900:
        raise ValueError('original Native receipt case or frame count differs')
    result_path = _source(root,'result.json')
    result = validate_result(_read(result_path))
    if result.get('case_id') != case or result.get('diagnostic_fixture') is not False:
        raise ValueError('saved result is not exact Native case')
    physical = result.get('physical_checks',{})
    if any(physical.get(name,{}).get('status') != 'met' for name in ('setup','attempt','maneuver','target')):
        raise ValueError('source-bound physical completion absent')
    trace_path = _source(root,'traffic_spec/trace.json')
    map_path = _source(root,result['video_frame_map_reference'])
    rows = [json.loads(line) for line in map_path.read_text().splitlines() if line]
    if len(rows) != 900 or any(row.get('video_frame') != index for index,row in enumerate(rows)):
        raise ValueError('original video frame map incomplete')
    native_rows = _read(_source(root,'actor-rows.json'))
    if len(native_rows) != 900 or any(a['frame'] != b['carla_frame'] or
            abs(a['time_s']-b['time_s']) > 1e-6 for a,b in zip(native_rows,rows)):
        raise ValueError('original Native time join differs')
    if result.get('video_references') != [name+'.mkv' for name in
            ('overview','approach','reference_corner','driver_reference')]:
        raise ValueError('four original camera references missing')
    for name in result['video_references']:
        if _sha(_source(root,name)) != sources.get(name):
            raise ValueError('original camera video differs from seal')
    video = _source(root,'final.mkv') if (root/'final.mkv').is_file() else _source(root,'raw.mkv')
    decode_receipt = Path(decode_receipt).resolve()
    if decode_receipt.exists():
        decoded = verify_receipt(video,decode_receipt,900,mapping_sha256=_sha(map_path))
    else:
        decoded = decode(video,900,mapping_sha256=_sha(map_path),receipt=decode_receipt)
    core = _read(trace_path)
    scenes = core.get('scenes')
    if not isinstance(scenes,list) or len(scenes) != 900 or any(
            scene.get('t') != round(row['time_s']*1000) for scene,row in zip(scenes,rows)):
        raise ValueError('Core trace/original timestamp join differs')
    physical_binding = {'native_result':_sha(result_path),'native_receipt':_sha(root/'native-receipt.json'),
                        'actor_rows':_sha(root/'actor-rows.json'),'trace':_sha(trace_path)}
    pixel_binding = {'video':_sha(video),'frame_map':_sha(map_path),
                     'decode_receipt':_sha(decode_receipt)}
    p = _review(_read(physical_review),kind='physical',case=case,binding=physical_binding)
    v = _review(_read(pixel_review),kind='pixel',case=case,binding=pixel_binding)
    actors = [str(receipt['subject_id'])]
    exception = receipt.get('exception_source')
    if exception:
        packet = _read(_source(root,exception['path']))
        for key in ('other_actor_id','officer_actor_id'):
            if key in packet: actors.append(str(packet[key]))
    if p.get('participant_actor_ids') != actors or v.get('visible_actor_ids') != actors:
        raise ValueError('independent participant review incomplete')
    if v.get('reviewed_frame_count') != 900 or v.get('four_camera_visibility') is not True:
        raise ValueError('actual four-camera pixel review incomplete')
    auditor = Path(auditor_path).resolve()
    if auditor.name != 'delivery_audit.py' or not auditor.is_file():
        raise ValueError('independent auditor file missing')
    return {'format':'worker-delivery-audit','passed':True,'case_id':case,
            'job_id':job_id,'attempt':attempt_number,'recording_id':recording_id,
            'checks':{key:True for key in CHECKS},'source_result_sha256':_sha(result_path),
            'native_receipt_sha256':_sha(root/'native-receipt.json'),
            'video':str(video.relative_to(root)),'video_sha256':_sha(video),
            'trace':str(trace_path.relative_to(root)),'trace_sha256':_sha(trace_path),
            'frames':900,'auditor_path':str(auditor),'auditor_sha256':_sha(auditor),
            'source_decode_receipt_path':str(decode_receipt),
            'source_decode_receipt_sha256':_sha(decode_receipt),
            'source_decode_auditor_sha256':decoded['auditor_sha256'],
            'physical_review_sha256':_sha(physical_review),'pixel_review_sha256':_sha(pixel_review),
            'legal_judgment':'unresolved'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',choices=('positive','stale'))
    parser.add_argument('--case',required=True)
    for arg in ('attempt','physical-review','pixel-review','decode-receipt',
                'job-id','recording-id','auditor-path','output'):
        parser.add_argument('--'+arg)
    parser.add_argument('--attempt-number',type=int)
    args=parser.parse_args()
    if args.self_test:
        if not args.case.startswith(ASSIGNMENT+'__'):
            raise ValueError('exact delivery identity missing')
        binding={'native_result':'a','native_receipt':'b','actor_rows':'c','trace':'d'}
        packet={'format':'crosswalk-independent-physical-review','case_id':args.case,
                'accepted':True,'source_hashes':binding,'reviewer':'CPU protocol fixture',
                'method':'review packet binding check','reviewed_frame_interval':[0,899]}
        if args.self_test == 'stale':binding={**binding,'trace':'changed'}
        _review(packet,kind='physical',case=args.case,binding=binding)
        print(json.dumps({'case_id':args.case,'review_binding_test':'passed',
                          'scope':'CPU checker fixture; no Native source or physical acceptance'}))
        return
    for name in ('attempt','physical_review','pixel_review','decode_receipt','job_id',
                 'recording_id','auditor_path','output','attempt_number'):
        if getattr(args,name) is None:parser.error('missing required argument: '+name)
    result=audit(args.attempt,args.case,args.physical_review,args.pixel_review,
                 args.decode_receipt,job_id=args.job_id,attempt_number=args.attempt_number,
                 recording_id=args.recording_id,auditor_path=args.auditor_path)
    output=Path(args.output)
    if output.exists():raise ValueError('retain previous independent audit')
    output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
