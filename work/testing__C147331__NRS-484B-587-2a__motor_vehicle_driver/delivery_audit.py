"""Independent source, pixel and physical audit for an exact saved lane case.

Diagnostic mode exercises rejection logic only. A passing diagnostic receipt
cannot be used for original Native delivery or any legal conclusion.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from saved_audit import audit_history

AID='testing__C147331__NRS-484B-587-2a__motor_vehicle_driver'
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode',
        'actual_pixels','physical_completion')


def need(ok,message):
    if not ok:raise ValueError(message)


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def decoded_frame_sha(path,frame):
    done=subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-vf',
                         'select=eq(n\\,'+str(frame)+')','-frames:v','1','-pix_fmt','rgb24',
                         '-f','rawvideo','-'],capture_output=True,check=True)
    need(done.stdout,'reviewed original frame has no decoded pixels')
    return sha256(done.stdout).hexdigest()


def original_capture(attempt,case):
    from worker_exchange.media import audit as media_audit
    seal_path=attempt/'capture-seal.json'
    need(seal_path.is_file(),'sealed original Native capture missing')
    seal=json.loads(seal_path.read_text())
    need(seal.get('provenance_kind')=='native' and seal.get('diagnostic_fixture') is False and
         seal.get('frames')==900 and seal.get('events')==['capture_finished','encoders_closed','restoration_verified'],
         'original Native closure or frame count missing')
    for name,checksum in seal.get('sources',{}).items():
        target=(attempt/name).resolve()
        need(target.is_relative_to(attempt) and target.is_file() and digest(target)==checksum,
             'sealed original Native source changed: '+name)
    receipt=json.loads((attempt/'original-source-receipt.json').read_text())
    need(receipt.get('case_id')==case and receipt.get('frame_count')==900 and
         receipt.get('source_kind')=='original_native_capture' and receipt.get('diagnostic_fixture') is False,
         'exact original source receipt differs')
    with (attempt/'original-history.jsonl').open() as source:
        map_sha256=json.loads(source.readline())['map_sha256']
    history=audit_history(attempt/'original-history.jsonl',receipt['history_sha256'],
                          case.removeprefix(AID+'__'),map_sha256)
    mapping_path=attempt/'video_frames.jsonl'
    mapping=[json.loads(line) for line in mapping_path.read_text().splitlines()]
    trace=[json.loads(line) for line in (attempt/'trace.jsonl').read_text().splitlines()]
    need(len(mapping)==len(trace)==900,'original time join incomplete')
    for index,(frame,motion) in enumerate(zip(mapping,trace)):
        need(frame.get('video_frame')==index and frame.get('carla_frame')==motion.get('frame') and
             abs(frame.get('time_s')-motion.get('time_s'))<1e-6,
             'original time join differs')
    bindings={}
    for name in CAMERAS:
        video=attempt/(name+'.mkv')
        need(video.is_file() and seal['sources'].get(video.name)==digest(video),
             'four original video sources missing')
        decoded=media_audit(video,900,mapping_sha256=digest(mapping_path))
        need(decoded.get('frames')==900,'original full video decode incomplete')
        bindings[video.name]=digest(video)
    return {'case_id':case,'frame_count':900,'full_decode':True,
            'receipt_sha256':digest(seal_path),'source_bindings':bindings,
            'original_history_sha256':history['original_history_sha256']}


def assess(case,capture,review,physical,*,diagnostic=False,attempt=None):
    need(case.startswith(AID+'__'),'exact delivery case required')
    need(capture.get('case_id')==case and capture.get('frame_count')==900 and
         capture.get('full_decode') is True,'original full capture audit missing')
    bindings=capture.get('source_bindings',{})
    need(set(name+'.mkv' for name in CAMERAS)<=set(bindings),
         'four original video sources missing')
    need(review.get('case_id')==case and review.get('capture_receipt_sha256')==capture.get('receipt_sha256'),
         'independent pixel review has wrong source')
    views=review.get('views')
    need(isinstance(views,dict) and set(views)==set(CAMERAS),
         'independent pixel review missing four views')
    need(review.get('legal_judgment') is None,'delivery audit cannot assert legal judgment')
    for name in CAMERAS:
        item=views[name]
        need(item.get('video_sha256')==bindings[name+'.mkv'] and
             isinstance(item.get('reviewer'),str) and item['reviewer'].strip(),
             'independent pixel review missing: '+name)
        samples=item.get('samples')
        need(isinstance(samples,list) and samples,
             'independent pixel samples missing: '+name)
        for sample in samples:
            frame=sample.get('frame')
            need(type(frame) is int and 0<=frame<900 and sample.get('vehicle_visible') is True and
                 sample.get('lane_boundary_visible') is True and sample.get('shoulder_visible') is True and
                 isinstance(sample.get('decoded_rgb_sha256'),str) and len(sample['decoded_rgb_sha256'])==64,
                 'independent participant and lane pixels incomplete: '+name)
            if not diagnostic:
                need(decoded_frame_sha(Path(attempt)/(name+'.mkv'),frame)==sample['decoded_rgb_sha256'],
                     'independent pixel source changed: '+name)
    maneuver=physical.get('physical_checks',{}).get('maneuver',{})
    need(physical.get('case_id')==case and physical.get('maneuver_completed') is True and
         maneuver.get('status')=='met' and maneuver.get('sources') and physical.get('realized_observables'),
         'source-measured physical completion missing')
    if not diagnostic:
        need(physical.get('provenance_kind')=='native' and physical.get('diagnostic_fixture') is False,
             'Native physical provenance required')
    return {'format':'worker-independent-delivery-audit','case_id':case,
            'checks':list(CHECKS),'capture_receipt_sha256':capture['receipt_sha256'],
            'source_verified':not diagnostic,'diagnostic_fixture':diagnostic,
            'canonical_acceptance':False,'legal_judgment':None}


def audit(case,attempt,review_path,physical_path,*,diagnostic_fixture=False):
    attempt=Path(attempt).resolve();review_path=Path(review_path).resolve()
    physical_path=Path(physical_path).resolve()
    need(review_path.is_file(),'independent pixel review missing')
    need(physical_path.is_file(),'physical result missing')
    if diagnostic_fixture:
        capture_path=attempt/'diagnostic-capture-audit.json'
        need(capture_path.is_file(),'diagnostic capture protocol missing')
        capture=json.loads(capture_path.read_text())
    else:capture=original_capture(attempt,case)
    review=json.loads(review_path.read_text())
    physical=json.loads(physical_path.read_text())
    result=assess(case,capture,review,physical,diagnostic=diagnostic_fixture,attempt=attempt)
    result['pixel_review_sha256']=digest(review_path)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True);parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True);parser.add_argument('--physical',type=Path,required=True)
    parser.add_argument('--diagnostic-fixture',action='store_true')
    args=parser.parse_args()
    print(json.dumps(audit(args.case,args.attempt,args.review,args.physical,
                           diagnostic_fixture=args.diagnostic_fixture),indent=2))
