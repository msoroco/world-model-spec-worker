"""Independent original-source acceptance audit for NRS 484B.473(2).

The CPU selftest inventories checks and rejects synthetic diagnostics. Actual
acceptance requires sealed Native pixels, source joins and saved-only output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

PREFIX='training__C229422__NRS-484B-473-2__motor_vehicle_driver__'
CASES={PREFIX+s for s in ('witness_1','witness_2','exception_1_1','exception_1_2')}
VIEWS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')


def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(row) for row in Path(path).read_text().splitlines()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_sources(case,attempt):
    config=read(attempt/'config.json');review=read(attempt/'lamp-pixel-review.json')
    scene=read(attempt/'original-scene-review.json')
    require(config.get('case_id')==case and review.get('case_id')==case and scene.get('case_id')==case,
            'Exact original case identity differs')
    require(review.get('source_kind')=='independent_original_review' and
            scene.get('source_kind')=='original_scene_setup',
            'Independent original optical and scene reviews missing')
    for label in ('highway','parking_rule','civil_clock','sunset_sunrise'):
        path=attempt/('original-'+label+'.json')
        require(scene.get('sources',{}).get(label,{}).get('sha256')==sha(path),
                'Original cited source changed: '+label)
    require(review.get('scene_sha256')==sha(attempt/'original-scene-review.json') and
            review.get('trace_sha256')==sha(attempt/'parked-lamp-trace.jsonl') and
            review.get('frame_map_sha256')==sha(attempt/'video_frames.jsonl'),
            'Independent review changed original trace, frame map or scene')
    for view in VIEWS:
        require(review.get('camera_sha256',{}).get(view)==sha(attempt/(view+'.mkv')),
                'Original optical review camera hash differs: '+view)
    trace=rows(attempt/'parked-lamp-trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    optical=review.get('optical_observations',[])
    require(len(trace)==len(mapping)==len(optical)==600,'Complete original 600-frame source join required')
    first_tick=mapping[0]['native_frame'];first_time=mapping[0]['native_elapsed_s']
    vehicle=trace[0].get('vehicle_actor_id')
    require(vehicle is not None,'Original parked vehicle actor missing')
    for i,(actor,frame,pixel) in enumerate(zip(trace,mapping,optical)):
        require(actor.get('source_kind')=='original_native_observation' and
                actor['video_frame']==frame['video_frame']==pixel['video_frame']==i and
                actor['native_frame']==frame['native_frame']==first_tick+i and
                abs(actor['native_elapsed_s']-frame['native_elapsed_s'])<1e-5 and
                abs(frame['native_elapsed_s']-first_time-i/20)<1e-4 and
                actor['vehicle_actor_id']==vehicle and actor['ego_speed_mps']<=0.1,
                'Original parked vehicle participant/frame/time join differs')
        require(pixel.get('source_camera') in VIEWS and pixel.get('pixel_box_xyxy') and
                all(type(pixel.get(key)) is bool for key in ('lights_displayed','depressed_or_dimmed',
                    'undepressed_headlamp','cowl_or_parking_used')),
                'Every original frame needs a reviewed optical pixel')
    require(all(review.get(k) is True for k in ('lawfully_parked','highway','civil_night')) and
            all(optical[i]['lights_displayed'] for i in range(600)),
            'Lawfully parked nighttime highway lamp activation unverified')
    mode=config.get('mode')
    patterns={'depressed_low_beam':(True,False,False),
              'undepressed_high_beam':(False,True,False),
              'undepressed_high_beam_with_parking':(False,True,True)}
    require(mode in patterns and all((p['depressed_or_dimmed'],p['undepressed_headlamp'],p['cowl_or_parking_used'])==patterns[mode] for p in optical),
            'Selected original lamp and parking pattern physically incomplete')
    return {'displayed_frames':600,'dimmed_frames':sum(p['depressed_or_dimmed'] for p in optical),
            'undepressed_frames':sum(p['undepressed_headlamp'] for p in optical),
            'parking_used_frames':sum(p['cowl_or_parking_used'] for p in optical)}


def audit(case,attempt,saved,output):
    require(case in CASES,'Select exact parked-lamp case')
    attempt,saved,output=Path(attempt).resolve(),Path(saved).resolve(),Path(output).resolve()
    provenance=read(attempt/'acquisition-provenance.json');seal=read(attempt/'capture-seal.json')
    require(provenance.get('provenance_kind')=='original_native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind')=='native' and seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format')=='worker-sealed-capture' and seal.get('frames')==600 and
            seal.get('events')==['capture_finished','encoders_closed','restoration_verified'] and
            seal.get('restoration',{}).get('restored') is True and
            all(seal.get('encoder_exit_codes',{}).get(view)==0 for view in VIEWS),
            'Original Native capture closure incomplete')
    for name,checksum in seal.get('sources',{}).items():
        require(sha(attempt/name)==checksum,'Sealed original source changed: '+name)
    exit_record,owner=read(attempt/'native-exit.json'),read(attempt/'owner-release.json')
    require(exit_record.get('capture_seal_sha256')==sha(attempt/'capture-seal.json') and
            owner.get('native_exit_sha256')==sha(attempt/'native-exit.json') and
            owner.get('event')=='owner_released',
            'Saved processing precedes Native exit or owner release')
    processing=read(saved/'processing.json')
    require(processing.get('case_id')==case and processing.get('passed') is True and
            processing.get('recorded_only') is True and processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False and
            processing.get('timestamp_joins',{}).get('frames')==600,
            'Saved-only original processing incomplete')
    result=read(Path(processing['result']).resolve())
    require(result.get('case_id')==case and result.get('provenance_kind')=='native' and
            result.get('diagnostic_fixture') is not True and
            result.get('legal_verdict_claimed') is False,
            'Saved original result provenance or legal scope differs')
    physical=inspect_sources(case,attempt)
    from worker_exchange.media import audit as decode
    decode_dir=output.parent/(case+'-source-decode');decode_dir.mkdir(parents=True,exist_ok=True)
    receipts={view:decode(attempt/(view+'.mkv'),600,receipt=decode_dir/(view+'.json'),
            mapping_sha256=sha(attempt/'video_frames.jsonl')) for view in VIEWS}
    core=Path(processing['version'])/'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes',[]))==600,
            'Saved original Core scene sequence unavailable')
    receipt={'format':'worker-delivery-audit','passed':True,'case_id':case,'frames':600,
        'checks':{name:True for name in CHECKS},'source_result_sha256':processing['result_sha256'],
        'video':'overview.mkv','video_sha256':sha(attempt/'overview.mkv'),
        'trace':str(core),'trace_sha256':sha(core),
        'source_decode_receipt_path':str(decode_dir/'overview.json'),
        'source_decode_receipt_sha256':sha(decode_dir/'overview.json'),
        'source_decode_auditor_sha256':receipts['overview']['auditor_sha256'],
        'auditor_path':str(Path(__file__).resolve()),'auditor_sha256':sha(__file__),
        'physical_observables':physical,'legal_verdict_claimed':False}
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def selftest(case,negative):
    require(case in CASES and len(VIEWS)==4 and len(CHECKS)==6,
            'Exact case or independent check inventory differs')
    scratch=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts,'Diagnostic scratch outside .runtime-work')
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt,saved=Path(temp)/'attempt',Path(temp)/'saved';attempt.mkdir();saved.mkdir()
        (attempt/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
        (attempt/'capture-seal.json').write_text(json.dumps({'format':'worker-sealed-capture','provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
        try:audit(case,attempt,saved,Path(temp)/'audit.json')
        except ValueError as error:
            require(str(error)=='Synthetic fixture cannot establish original Native delivery',
                    'Synthetic fixture rejected for wrong reason')
            if negative:raise
        else:raise AssertionError('Synthetic fixture passed original delivery')
    print('PASS six original-source checks inventoried; synthetic delivery rejected')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--selftest',action='store_true')
    p.add_argument('--negative-fixture',action='store_true');p.add_argument('--attempt');p.add_argument('--saved');p.add_argument('--output')
    a=p.parse_args()
    if a.selftest:selftest(a.case,a.negative_fixture)
    else:print(json.dumps(audit(a.case,a.attempt,a.saved,a.output),sort_keys=True))
