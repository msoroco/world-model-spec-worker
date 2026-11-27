"""Independent source-bound comparison of parked lamp and parking-lamp use.

A request contrast is accepted only with reviewed original pixels and common
parking/nighttime context. No categorical lamp request is a legal cutoff.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

PREFIX='training__C229422__NRS-484B-473-2__motor_vehicle_driver__'
PAIRS={'witness':('witness_1','witness_2'),
       'exception':('exception_1_1','exception_1_2')}
VIEWS=('overview','approach','reference_corner','driver_reference')


def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(row) for row in Path(path).read_text().splitlines()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root):
    root=Path(root);config=read(root/'config.json');review=read(root/'lamp-pixel-review.json')
    trace=rows(root/'parked-lamp-trace.jsonl');mapping=rows(root/'video_frames.jsonl')
    require(len(trace)==len(mapping)==600 and len(review.get('optical_observations',[]))==600,
            'Complete original lamp frame/time and pixel joins required')
    require(review.get('case_id')==config.get('case_id'),'Exact source pixel review required')
    for view in VIEWS:
        require(review.get('camera_sha256',{}).get(view)==sha(root/(view+'.mkv')),
                'Source camera hash differs: '+view)
    first=mapping[0]['native_frame'];origin=mapping[0]['native_elapsed_s']
    for i,(actor,frame,pixel) in enumerate(zip(trace,mapping,review['optical_observations'])):
        require(actor['video_frame']==frame['video_frame']==pixel['video_frame']==i and
                actor['native_frame']==frame['native_frame']==first+i and
                abs(actor['native_elapsed_s']-frame['native_elapsed_s'])<1e-5 and
                abs(frame['native_elapsed_s']-origin-i/20)<1e-4 and
                actor['ego_speed_mps']<=0.1,
                'Original parked lamp time join or stopped state differs')
        require(pixel.get('source_camera') in VIEWS and pixel.get('pixel_box_xyxy') and
                all(type(pixel.get(key)) is bool for key in ('lights_displayed','depressed_or_dimmed',
                    'undepressed_headlamp','cowl_or_parking_used')),
                'Original optical pixel evidence incomplete')
    require(all(review.get(key) is True for key in ('lawfully_parked','civil_night','highway')),
            'Lawful highway nighttime context unverified')
    return {'config':config,'review':review,'trace':trace,'mapping':mapping,
            'optical':review['optical_observations'],
            'source_sha256':sha(root/'parked-lamp-trace.jsonl'),
            'camera_sha256':{view:sha(root/(view+'.mkv')) for view in VIEWS}}


def compare(reference,contrast,kind):
    require(kind in PAIRS,'Unknown exact lamp comparison')
    left,right=source(reference),source(contrast)
    a,b=PAIRS[kind]
    require(left['config']['case_id']==PREFIX+a and right['config']['case_id']==PREFIX+b,
            'Exact comparison case order differs')
    for key in ('law_id','cell_id','actor','frozen_cell','cameras','duration_frames','duration_s','rate_hz','vehicle_blueprint'):
        require(left['config'][key]==right['config'][key],'Fixed construction changed: '+key)
    for key in ('lawfully_parked','highway','civil_night'):
        require(left['review'][key]==right['review'][key], 'Fixed reviewed context changed: '+key)
    for name in ('highway','parking_rule','civil_clock','sunset_sunrise'):
        require(read(Path(reference)/('original-'+name+'.json'))==read(Path(contrast)/('original-'+name+'.json')),
                'Fixed cited context source changed: '+name)
    left_pixels,right_pixels=left['optical'],right['optical']
    require(all(p['lights_displayed'] for p in left_pixels+right_pixels),
            'Displayed lamp activation is unverified')
    if kind=='witness':
        require(left['config']['mode']=='depressed_low_beam' and right['config']['mode']=='undepressed_high_beam',
                'Selected headlamp request contrast differs')
        require(all(p['depressed_or_dimmed'] and not p['cowl_or_parking_used'] for p in left_pixels) and
                all(p['undepressed_headlamp'] and not p['cowl_or_parking_used'] for p in right_pixels),
                'Reviewed low versus high headlamp contrast missing')
        difference='headlamp request and observed dimmed/undepressed pixels'
    else:
        require(left['config']['mode']=='undepressed_high_beam' and
                right['config']['mode']=='undepressed_high_beam_with_parking',
                'Selected parking-lamp request contrast differs')
        require(all(p['undepressed_headlamp'] and not p['cowl_or_parking_used'] for p in left_pixels) and
                all(p['undepressed_headlamp'] and p['cowl_or_parking_used'] for p in right_pixels),
                'Reviewed parking-lamp exception contrast missing')
        difference='parking lamp request and observed use with high headlamps fixed'
    return {'format':'worker-independent-parked-lamp-comparison','passed':True,
            'case_ids':[PREFIX+a,PREFIX+b],'source_sha256':[left['source_sha256'],right['source_sha256']],
            'controlled_difference':difference,'fixed_conditions':['frozen cell','lawful highway parking and civil nighttime',
                'four-camera plan','600-frame 20-Hz interval'],
            'observed_depressed_frames':[sum(p['depressed_or_dimmed'] for p in left_pixels),
                                         sum(p['depressed_or_dimmed'] for p in right_pixels)],
            'observed_parking_frames':[sum(p['cowl_or_parking_used'] for p in left_pixels),
                                       sum(p['cowl_or_parking_used'] for p in right_pixels)],
            'legal_conclusion':None,'physical_acceptance_claimed':False}


def selftest():
    scratch=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts,'Scratch must be under .runtime-work')
    results=[]
    for kind,(a,b) in PAIRS.items():
        left=scratch/('attempt-'+a+'-final');right=scratch/('attempt-'+b+'-final')
        results.append(compare(left,right,kind))
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            altered=Path(temp)/'altered';shutil.copytree(right,altered)
            config=read(altered/'config.json');config['cameras'][0]['fov_deg']=75
            (altered/'config.json').write_text(json.dumps(config)+'\n')
            try:compare(left,altered,kind)
            except ValueError as error:
                require('Fixed construction changed: cameras' in str(error),'Wrong fixed-condition rejection')
            else:raise AssertionError('Altered camera plan accepted')
    return {'format':'worker-parked-lamp-comparison-selftest','passed':True,
            'positive':results,'altered_camera_rejected':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true')
    p.add_argument('--reference');p.add_argument('--contrast');p.add_argument('--kind',choices=tuple(PAIRS));p.add_argument('--output')
    a=p.parse_args()
    if a.selftest:print(json.dumps(selftest(),sort_keys=True))
    else:
        result=compare(a.reference,a.contrast,a.kind)
        Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'passed':True,'case_ids':result['case_ids']}))
