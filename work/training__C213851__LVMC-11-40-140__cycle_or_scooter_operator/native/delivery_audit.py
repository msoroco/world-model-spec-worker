"""Independent source, pixel, timing and physical crossing audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[1]
AID=HERE.name
VIEWS=('overview','approach','reference_corner','driver_reference')
SIZES={name:((1920,1080) if name=='overview' else (1280,720)) for name in VIEWS}


def require(condition,message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root,name):
    root=Path(root).resolve()
    path=(root/name).resolve()
    require(root in path.parents and path.is_file(),'Missing delivery source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path,size=None):
    run=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames,width,height,r_frame_rate','-of','json',str(path)],
        capture_output=True,text=True,timeout=180)
    require(run.returncode==0,'Full video decode failed')
    streams=json.loads(run.stdout).get('streams',[])
    require(len(streams)==1,'Full video stream inventory differs')
    meta=streams[0]
    require(meta.get('nb_read_frames')=='600' and meta.get('r_frame_rate')=='20/1',
        'Full video frame count or rate differs')
    if size:
        require((int(meta['width']),int(meta['height']))==size,'Full video dimensions differ')
    pixel=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
        '-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],
        capture_output=True,timeout=180)
    require(pixel.returncode==0 and len(pixel.stdout)==int(meta['width'])*int(meta['height'])*3,
        'Actual decoded pixels absent')
    return {'frames':600,'rate_hz':20,'width':int(meta['width']),'height':int(meta['height']),
        'sha256':sha(path),'first_frame_rgb_sha256':hashlib.sha256(pixel.stdout).hexdigest()}


def audit(root,case,diagnostic=False):
    suffix=case.rsplit('__',1)[-1]
    require(case==AID+'__'+suffix and suffix in ('probe_01','probe_02'),
        'Wrong sidewalk crossing delivery case')
    names=('video_frames.jsonl','sidewalk-native.jsonl','sidewalk_context.json','trace.jsonl')
    paths={name:source(root,name) for name in names}
    frames,native,trace=(rows(paths[name]) for name in
        ('video_frames.jsonl','sidewalk-native.jsonl','trace.jsonl'))
    context=json.loads(paths['sidewalk_context.json'].read_text())
    require(context.get('assignment_id')==AID and context.get('case_id')==case and
        context.get('district')=='residence' and context.get('origin_kind')=='driveway' and
        context.get('travel_direction')=='into_driveway' and
        context.get('rider_class')=='bicycle','Selected residence-driveway rider source differs')
    require(context.get('review_kind')==('synthetic_diagnostic' if diagnostic else 'original_source_review'),
        'Original sidewalk source review absent')
    for field in ('district_source_id','origin_source_id','sidewalk_continuation_source_id',
                  'sidewalk_boundary_source_id','rider_class_source_id','pedestrian_conflict_source_id'):
        require(context.get(field),'Missing reviewed crossing source: '+field)
    require(context.get('sidewalk_continuation_across_origin') is True and
        len(context.get('pedestrian_conflict_polygon_xy_m',[]))>=3,
        'Sidewalk continuation or pedestrian conflict geometry unverified')
    require(len(frames)==len(native)==len(trace)==600,'Native rider/pedestrian trace join incomplete')
    rider_ids={row.get('rider_id') for row in native}
    pedestrian_ids={row.get('pedestrian_id') for row in native}
    require(len(rider_ids)==len(pedestrian_ids)==1 and rider_ids!=pedestrian_ids,
        'Distinct rider/pedestrian identities missing')
    for i,(frame,row,pose) in enumerate(zip(frames,native,trace)):
        require(frame.get('video_frame')==row.get('frame')==i and
            frame.get('native_frame')==row.get('native_frame')==pose.get('frame') and
            abs(frame['time_s']-pose['time_s'])<1e-4 and
            abs(row['rider_speed_mps']-pose['speed_mps'])<1e-8 and
            abs(row['rider_x_m']-pose['position_m'][0])<1e-8,
            'Native rider/pedestrian frame or pose differs')
    require(frames[-1]['time_s']-frames[0]['time_s']>=29.9,
        'Full 30-second source period missing')
    if diagnostic:
        video=decode(source(root,'diagnostic.mkv'))
        proof=json.loads((HERE/'physical-proof'/suffix/'complete_motion.json').read_text())
        require(proof['physical_checks']['maneuver']['status']=='met' and
            proof['diagnostic_fixture'] is True,'Diagnostic physical fixture not met')
        return {'format':'worker-lvmc-sidewalk-source-audit-v1','case_id':case,
            'diagnostic_fixture':True,'native_executed':False,
            'source_join_frames':600,'synthetic_pixel_decode':video,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    videos={name:decode(source(root,name+'.mkv'),SIZES[name]) for name in VIEWS}
    review_path=source(root,'sidewalk-original-review.json')
    review=json.loads(review_path.read_text())
    require(all(review.get(key) is True for key in
        ('original_pixel_reviewed','district_and_driveway_reviewed',
         'sidewalk_continuation_reviewed','rider_pedestrian_identity_reviewed',
         'stop_and_conflict_reviewed')),
        'Original sidewalk, rider and pedestrian review missing')
    require(review.get('camera_sha256')=={v+'.mkv':videos[v]['sha256'] for v in VIEWS} and
        review.get('source_sha256')=={name:sha(path) for name,path in paths.items()},
        'Original source review hash differs')
    result=json.loads(source(root,'result.json').read_text())
    require(result.get('case_id')==case and result.get('maneuver_completed') is True and
        result.get('physical_checks',{}).get('maneuver',{}).get('status')=='met',
        'Original Native physical completion unverified')
    return {'format':'worker-lvmc-sidewalk-source-audit-v1','case_id':case,'passed':True,
        'native_executed':True,'checks':['native_source','all_participants','time_join',
            'full_video_decode','actual_pixels','physical_completion'],
        'source_sha256':{name:sha(path) for name,path in paths.items()},
        'video_decode':videos,'review_sha256':sha(review_path),'legal_verdict_claimed':False}


def selftest(case,negative):
    suffix=case.rsplit('__',1)[-1]
    require(case==AID+'__'+suffix,'Wrong selftest case')
    diagnostic=json.loads((HERE/'cases'/suffix/'diagnostic.json').read_text())
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='c213851-source-audit-') as tmp:
        stage=Path(tmp)
        for name in ('video_frames.jsonl','sidewalk-native.jsonl','sidewalk_context.json','trace.jsonl'):
            (stage/name).write_text(diagnostic['files'][name])
        if negative:
            (stage/'sidewalk-native.jsonl').unlink()
        else:
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                '-i','color=c=black:s=64x36:r=20','-frames:v','600','-an','-c:v','ffv1',
                '-threads','1',str(stage/'diagnostic.mkv')],check=True,timeout=180)
        return audit(stage,case,diagnostic=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--negative-selftest',action='store_true')
    args=parser.parse_args()
    result=selftest(args.case,args.negative_selftest) if (args.selftest or args.negative_selftest) else audit(args.attempt,args.case)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
