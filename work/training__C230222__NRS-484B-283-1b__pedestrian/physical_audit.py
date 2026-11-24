"""Fail-closed review of original curb motion, video pixels and exception context."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

CAMERAS=('overview','approach','reference_corner','driver_reference')
CROSSREFS=('NRS-484B-287-1c','NRS-484B-287-1d','NRS-484B-287-1e',
           'LVMC-11-30-060-A','LVMC-11-30-060-B','LVMC-11-30-140-B','LVMC-11-46-030')


def validate_cross_reference_review(crossrefs):
    if not isinstance(crossrefs,dict) or set(crossrefs)!=set(CROSSREFS):
        raise ValueError('Exact introductory cross-reference review required')
    if any(item not in ('applicable','inapplicable') for item in crossrefs.values()):
        raise ValueError('Unresolved introductory cross-reference applicability')
    return crossrefs


def validate_cross_reference_evidence(evidence, reviewed_frames):
    if not isinstance(evidence,dict) or set(evidence)!=set(CROSSREFS):
        raise ValueError('Exact introductory cross-reference evidence required')
    for law_id, item in evidence.items():
        if not isinstance(item,dict):
            raise ValueError('Cross-reference evidence missing: '+law_id)
        frames=item.get('frames')
        cameras=item.get('cameras')
        observation=item.get('observation')
        if (not isinstance(frames,list) or not frames or
            any(not isinstance(frame,int) or frame not in reviewed_frames for frame in frames) or
            not isinstance(cameras,list) or not cameras or
            any(camera not in CAMERAS for camera in cameras) or
            not isinstance(observation,str) or not observation.strip()):
            raise ValueError('Cross-reference source frames or observation missing: '+law_id)
    return evidence


def validate_road_context(context, road_sha256):
    if (not isinstance(context,dict) or
        context.get('source_kind')!='native_observation' or
        context.get('frozen_cell') != {'layout':'road','maneuver':'travel','control':'curb'} or
        context.get('authored_road_sha256')!=road_sha256 or
        not isinstance(context.get('native_road_sha256'),str) or
        re.fullmatch(r'[0-9a-f]{64}',context['native_road_sha256']) is None):
        raise ValueError('Original Native road and frozen curb cell source join required')
    return context['native_road_sha256']


def validate_native_road_source(content, expected_sha256):
    if hashlib.sha256(content).hexdigest()!=expected_sha256:
        raise ValueError('Generated Native map source hash differs')
    root=ET.fromstring(content)
    road_count=len(root.findall('road'))
    junction_count=len(root.findall('junction'))
    signal_count=len(root.findall('.//signals/signal'))
    crosswalk_count=sum(item.get('type')=='crosswalk'
                        for item in root.findall('.//objects/object'))
    if road_count<1 or junction_count or signal_count or crosswalk_count:
        raise ValueError('Generated Native map has unexpected intersection or device context')
    return {'road_count':road_count,'junction_count':junction_count,
            'signal_count':signal_count,'crosswalk_count':crosswalk_count}


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
    context_path=attempt/'curb-context.json'
    context=read(context_path)
    if data.get('curb_context_sha256')!=sha(context_path):
        raise ValueError('Original Native curb context review binding required')
    native_road_sha=validate_road_context(context,sha(attempt/'road.xodr'))
    native_road_path=attempt/'native-road.xodr'
    if context.get('native_road_source')!='native-road.xodr' or not native_road_path.is_file():
        raise ValueError('Generated Native OpenDRIVE source required')
    native_road_shape=validate_native_road_source(native_road_path.read_bytes(),native_road_sha)
    if data.get('native_road_source_sha256')!=native_road_sha:
        raise ValueError('Original Native map review binding required')
    checks=('curb_and_place_of_safety_pixels_verified','pedestrian_footprint_pixels_verified',
            'approaching_vehicle_pixels_verified','physical_completion_reviewed',
            'vehicle_response_reviewed','driver_yield_capability_reviewed')
    if not all(data.get(key) is True for key in checks):
        raise ValueError('Original pixels, vehicle response or driver capability unverified')
    crossrefs=validate_cross_reference_review(data.get('cross_reference_applicability'))
    frames=data.get('reviewed_frames')
    if not isinstance(frames,list) or not frames or any(
            not isinstance(frame,int) or frame<0 or frame>=600 for frame in frames):
        raise ValueError('Original review frame identities missing')
    crossref_evidence=validate_cross_reference_evidence(
        data.get('cross_reference_evidence'),frames)
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
            'curb_context_sha256':sha(context_path),
            'authored_road_sha256':context['authored_road_sha256'],
            'native_road_sha256':native_road_sha,
            'native_road_shape':native_road_shape,
            'source_video_sha256':hashes,'decoded_frames':decoded,
            'reviewed_frames':frames,'cross_reference_applicability':crossrefs,
            'cross_reference_evidence':crossref_evidence,
            'physical_completion_reviewed':True,'legal_verdict':None}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--review',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt,args.review),indent=2)+'\n')
