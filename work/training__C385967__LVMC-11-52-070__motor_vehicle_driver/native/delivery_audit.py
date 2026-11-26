"""Independent source, video and reviewed-pixel audit of an angle-park attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from physical_preparation import assess
from saved_measure import NAMES, sha

CAMERAS = ('overview','approach','reference_corner','driver_reference')
CHECKS = ('native_source','all_participants','time_join','full_video_decode',
          'actual_pixels','physical_completion')


def require(ok, message):
    if not ok: raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def video(path):
    result = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-count_frames','-show_entries','stream=nb_read_frames,width,height',
        '-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
    item=json.loads(result.stdout)['streams'][0]
    require(int(item['nb_read_frames'])==600,'Full source video decode differs')
    return int(item['width']),int(item['height'])


def check_review(review,case,hashes,dimensions,source_kind):
    require(review.get('format')=='c385967-independent-review-v1' and
            review.get('case_id')==case and review.get('source_kind')==source_kind and
            review.get('legal_verdict') is None,
            'Independent review identity differs')
    for name,digest in hashes.items():
        require(review.get('source_hashes',{}).get(name)==digest,
                'Independent review source stale: '+name)
    require(set(CHECKS)<=set(review.get('checks',[])),
            'Independent delivery checks missing')
    require(all(review.get(key) is True for key in
                ('physical_completion','city_engineer_street_document_reviewed',
                 'original_marking_readback_reviewed','original_parked_activity_reviewed',
                 'lawful_one_way_direction_reviewed','front_orientation_reviewed')),
            'Original City designation, physical or visual review incomplete')
    claims={'vehicle','bay_marking','regulatory_sign','lawful_direction','parked_front'}
    boxes=review.get('pixel_boxes',[])
    require(claims<={b.get('claim') for b in boxes},'Original reviewed pixel claims missing')
    for box in boxes:
        camera=box.get('source');rect=box.get('rect_xywh')
        require(camera in CAMERAS and type(box.get('frame')) is int and
                0<=box['frame']<600 and isinstance(rect,list) and len(rect)==4 and
                all(type(v) is int and v>=0 for v in rect) and
                rect[2]>0 and rect[3]>0,'Reviewed pixel box invalid')
        w,h=dimensions[camera]
        require(rect[0]+rect[2]<=w and rect[1]+rect[3]<=h,
                'Reviewed pixel box exceeds source video')


def audit(case,attempt,review_path):
    attempt=Path(attempt).resolve()
    config=read(attempt/'config.json')
    require(config.get('case_id')==case,'Exact selected case differs')
    geometry=read(attempt/'road_geometry.json')
    require(geometry.get('provenance')=='original_native_capture',
            'Original Native road source required')
    hashes={}
    for name in (*NAMES,'trace.jsonl','capture/evidence.jsonl','capture/manifest.json',
                 *(c+'.mkv' for c in CAMERAS)):
        path=attempt/name
        require(path.is_file(),'Missing original source: '+name)
        hashes[name]=sha(path)
    capture=read(attempt/'capture/manifest.json')
    require(capture.get('synthetic_diagnostic') is not True and
            capture.get('frames')==600,'Synthetic diagnostic cannot be original delivery')
    samples,mapping,trace=(rows(attempt/n) for n in
                           ('native_samples.jsonl','video_frames.jsonl','trace.jsonl'))
    require(len(samples)==len(mapping)==len(trace)==600,'Original 600-frame join differs')
    for i,(sample,frame,motion) in enumerate(zip(samples,mapping,trace)):
        require(frame['video_frame']==i and
                frame['native_frame']==sample['native_frame']==motion['frame'] and
                abs(frame['time_s']-sample['time_s'])<.001 and
                abs(motion['time_s']-sample['time_s'])<.001,
                'Original Native/time join differs')
    physical=assess(attempt,config)
    require(physical['status']=='met','Original parked pose and rest unproved')
    dimensions={name:video(attempt/(name+'.mkv')) for name in CAMERAS}
    review_path=Path(review_path)
    check_review(read(review_path),case,hashes,dimensions,'original_native')
    return {'format':'worker-delivery-audit','case_id':case,'checks':list(CHECKS),
        'passed':True,'source_hashes':hashes,'review_sha256':sha(review_path),
        'physical_acceptance_claimed':False,'legal_verdict':None}


def selftest(case,negative):
    suffix=case.rsplit('_',1)[-1]
    require(suffix in ('a','b'),'Unknown angle case')
    root=Path(__file__).resolve().parents[3]/'.runtime-work/c385967-source-proof'
    attempt=root/('probe_'+suffix)
    require(attempt.is_dir(),'Source-shaped CPU fixture absent')
    hashes={name:sha(attempt/name) for name in NAMES}
    dimensions={name:video(attempt/(name+'.mkv')) for name in CAMERAS}
    review={'format':'c385967-independent-review-v1','case_id':case,
        'source_kind':'synthetic_cpu_mechanics','legal_verdict':None,
        'source_hashes':hashes,'checks':list(CHECKS),
        'physical_completion':True,'city_engineer_street_document_reviewed':True,
        'original_marking_readback_reviewed':True,'original_parked_activity_reviewed':True,
        'lawful_one_way_direction_reviewed':True,'front_orientation_reviewed':True,
        'pixel_boxes':[{'claim':claim,'source':CAMERAS[i%4],
            'frame':100+i,'rect_xywh':[0,0,4,4]} for i,claim in enumerate(
            ('vehicle','bay_marking','regulatory_sign','lawful_direction','parked_front'))]}
    if negative:
        review['pixel_boxes'][0]['rect_xywh'][0]=dimensions['overview'][0]
    check_review(review,case,hashes,dimensions,'synthetic_cpu_mechanics')
    require(not negative,'Negative review was accepted')
    return {'case_id':case,'passed':True,'joined_frames':600,
            'scope':'synthetic CPU mechanics only; no City permission or Native delivery accepted'}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True)
    p.add_argument('--attempt')
    p.add_argument('--review')
    p.add_argument('--selftest',action='store_true')
    p.add_argument('--negative-selftest',action='store_true')
    a=p.parse_args()
    if a.selftest or a.negative_selftest:
        print(json.dumps(selftest(a.case,a.negative_selftest),sort_keys=True))
    else:
        require(a.attempt and a.review,'Original delivery paths required')
        print(json.dumps(audit(a.case,a.attempt,a.review),sort_keys=True))
