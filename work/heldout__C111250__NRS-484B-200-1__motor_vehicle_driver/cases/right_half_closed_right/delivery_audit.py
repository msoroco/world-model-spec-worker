"""Independent saved-source audit for C111250 road-half cases.

This is a CPU proof of source completeness and decoder compatibility. It never
asserts that a CARLA maneuver, visual feature, or legal exception was realized.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('c111250_road_half',HERE/'road_half.py')
road_half=importlib.util.module_from_spec(spec)
spec.loader.exec_module(road_half)
CAMERAS=('overview','approach','reference_corner','driver_reference')

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def _camera(root,name,original_frames,original_times):
    video=root/(name+'.mkv')
    frame_source=root/(name+'-frames.jsonl')
    if not video.is_file() or not frame_source.is_file():
        raise ValueError('Missing original camera source: '+name)
    rows=_rows(frame_source)
    if ([row.get('carla_frame') for row in rows]!=original_frames or
            [row.get('time_s') for row in rows]!=original_times):
        raise ValueError('Original camera/frame identity join failed: '+name)
    probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                          '-show_entries','stream=nb_read_frames,width,height,r_frame_rate',
                          '-of','json',str(video)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout).get('streams',[])
    if len(streams)!=1 or int(streams[0].get('nb_read_frames',-1))!=len(original_frames):
        raise ValueError('Original camera encoded frame count differs: '+name)
    decoded=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(video),'-f','null','-'],
                           capture_output=True,text=True)
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError('Original camera full decode failed: '+name)
    return {'video_sha256':_sha(video),'frame_source_sha256':_sha(frame_source),
            'frames':len(rows),'width':int(streams[0]['width']),'height':int(streams[0]['height'])}

def audit_delivery(root, *, expected_frames):
    root=Path(root)
    measured=road_half.measure_saved(root,expected_frames=expected_frames)
    frames=measured['original_frames'];times=measured['original_times_s']
    cameras={name:_camera(root,name,frames,times) for name in CAMERAS}
    return {'format':'c111250-source-delivery-audit','case_measurement':measured,
            'camera_sources':cameras,'source_join_complete':True,
            'fixture_or_native_physical_outcome_unverified':True,
            'legal_exception_judgment':None}

def audit_comparison(left_root,right_root,variable,*,expected_frames):
    left=audit_delivery(left_root,expected_frames=expected_frames)
    right=audit_delivery(right_root,expected_frames=expected_frames)
    a=left['case_measurement'];b=right['case_measurement']
    for result,root in ((a,Path(left_root)),(b,Path(right_root))):
        plan=json.loads((root/'capture_contract.json').read_text())
        actor=json.loads((root/'actor_identity.json').read_text())
        if set(plan.get('cameras',[]))!=set(CAMERAS) or plan.get('rate_hz')!=20:
            raise ValueError('Fixed four-camera capture plan missing')
        if plan.get('expected_frames')!=expected_frames or not actor.get('subject_blueprint'):
            raise ValueError('Fixed actor/duration source missing')
        road=json.loads((root/'road_geometry.json').read_text())
        result.update(road_hash=result['source_sha256']['road_geometry.json'],
                      centerline_hash=hashlib.sha256(json.dumps(road['centerline'],sort_keys=True).encode()).hexdigest(),
                      camera_plan_hash=_sha(root/'capture_contract.json'),
                      duration_s=plan['duration_s'],actor_hash=_sha(root/'actor_identity.json'))
    comparison=road_half.audit_comparison(a,b,variable)
    if variable=='body_side':
        if a['source_sha256'].get('exception_context.json')!=b['source_sha256'].get('exception_context.json'):
            raise ValueError('Fixed original exception premise differs')
    return {'comparison':comparison,'left_source_sha256':a['source_sha256'],
            'right_source_sha256':b['source_sha256'],'legal_exception_judgment':None}
