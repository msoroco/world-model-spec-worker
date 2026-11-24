"""Fail-closed review of original curb motion, video pixels and exception context."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS=('overview','approach','reference_corner','driver_reference')
CROSSREFS=('NRS-484B-287-1c','NRS-484B-287-1d','NRS-484B-287-1e',
           'LVMC-11-30-060-A','LVMC-11-30-060-B','LVMC-11-30-140-B','LVMC-11-46-030')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file(): raise ValueError('Original Native source required: '+path.name)
    return json.loads(path.read_text())


def audit(attempt,review):
    attempt,review=Path(attempt),Path(review)
    config=read(attempt/'config.json')
    capture_path=attempt/'native-capture-report.json'
    report=read(capture_path)
    if (report.get('case_id')!=config['case_id'] or report.get('frames')!=600 or
            report.get('error') is not None or not report.get('restoration')):
        raise ValueError('Complete restored Native curb capture required')
    data=read(review)
    if (data.get('case_id')!=config['case_id'] or
            data.get('native_capture_report_sha256')!=sha(capture_path) or
            data.get('provenance')!='original_native' or not data.get('reviewer')):
        raise ValueError('Independent original Native review binding required')
    checks=('curb_and_place_of_safety_pixels_verified','pedestrian_footprint_pixels_verified',
            'approaching_vehicle_pixels_verified','physical_completion_reviewed',
            'vehicle_response_reviewed','driver_yield_capability_reviewed')
    if not all(data.get(key) is True for key in checks):
        raise ValueError('Original pixels, vehicle response or driver capability unverified')
    crossrefs=data.get('cross_reference_applicability')
    if not isinstance(crossrefs,dict) or set(crossrefs)!=set(CROSSREFS) or any(
            item not in ('applicable','inapplicable','unresolved') for item in crossrefs.values()):
        raise ValueError('Exact introductory cross-reference review required')
    frames=data.get('reviewed_frames')
    if not isinstance(frames,list) or not frames or any(
            not isinstance(frame,int) or frame<0 or frame>=600 for frame in frames):
        raise ValueError('Original review frame identities missing')
    hashes=data.get('source_video_sha256')
    if not isinstance(hashes,dict) or set(hashes)!=set(CAMERAS):
        raise ValueError('Four original source videos required')
    decoded={}
    for camera in CAMERAS:
        video=attempt/(camera+'.mkv')
        if not video.is_file() or sha(video)!=hashes[camera]:
            raise ValueError('Original camera video hash differs: '+camera)
        probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                              '-show_entries','stream=nb_read_frames',
                              '-of','default=nokey=1:noprint_wrappers=1',str(video)],
                             capture_output=True,text=True,check=True)
        if probe.stdout.strip()!='600':
            raise ValueError('Complete original camera decode required: '+camera)
        decoded[camera]=600
    return {'format':'c230222-original-physical-review-v1','case_id':config['case_id'],
            'native_capture_report_sha256':sha(capture_path),
            'source_video_sha256':hashes,'decoded_frames':decoded,
            'reviewed_frames':frames,'cross_reference_applicability':crossrefs,
            'physical_completion_reviewed':True,'legal_verdict':None}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--review',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt,args.review),indent=2)+'\n')
