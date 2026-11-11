"""Independent CPU audit of original C10301 speed and four-camera sources.

A positive result means source closure and software decode passed. It is not a
physical completion, public-highway, or legal acceptance decision.
"""
import hashlib
import json
import math
from pathlib import Path

CAMERAS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def audit(attempt:Path,case_id:str,media_auditor=None)->dict:
    attempt=Path(attempt)
    if media_auditor is None:
        from worker_exchange.media import audit as media_auditor
    config_path=attempt/'config.json';result_path=attempt/'result.json'
    for path in (config_path,result_path,attempt/'subject_motion.jsonl',attempt/'video_frames.jsonl',attempt/'trace.jsonl',attempt/'capture/evidence.jsonl',*(attempt/name for name in CAMERAS)):
        if not path.is_file():raise ValueError('Missing original source: '+str(path.relative_to(attempt)))
    config=json.loads(config_path.read_text());result=json.loads(result_path.read_text())
    if config.get('selected_case_id')!=case_id or result.get('case_id')!=case_id:raise ValueError('Case identity mismatch')
    if sorted(result.get('video_references',[]))!=sorted(CAMERAS):raise ValueError('Four source cameras not bound in result')
    motion,mapping,trace=_rows(attempt/'subject_motion.jsonl'),_rows(attempt/'video_frames.jsonl'),_rows(attempt/'trace.jsonl')
    if not motion or len(motion)!=len(mapping) or len(trace)!=len(mapping):raise ValueError('Incomplete original frame streams')
    prev=(-1,-math.inf);speeds=[]
    for i,(m,f,t) in enumerate(zip(motion,mapping,trace)):
        frame,time=m.get('frame'),m.get('time_s')
        if type(frame) is not int or type(time) not in (int,float) or not math.isfinite(time) or frame<=prev[0] or time<=prev[1]:
            raise ValueError('Nonmonotone original motion')
        prev=frame,time
        if f.get('video_frame')!=i or f.get('carla_frame')!=frame or f.get('time_s')!=time or t.get('frame')!=frame or t.get('time_s')!=time:
            raise ValueError('Original frame join mismatch')
        xyz=m.get('velocity_mps')
        if m.get('speed_source')!='actor.get_velocity' or not isinstance(xyz,list) or len(xyz)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xyz):
            raise ValueError('Original Native velocity missing')
        speed=math.sqrt(sum(v*v for v in xyz))
        if abs(speed-m.get('speed_mps',float('nan')))>1e-6 or abs(speed-t.get('speed_mps',float('nan')))>1e-6:
            raise ValueError('Original speed disagrees with velocity')
        speeds.append(speed)
    peak=max(speeds)/0.44704
    measured=result.get('measured_values',{}).get('sampled_peak_speed_mph')
    if type(measured) not in (int,float) or not math.isfinite(measured) or abs(peak-measured)>1e-4:
        raise ValueError('Finalized peak speed differs from original velocity')
    for name in ('subject_motion.jsonl','video_frames.jsonl','road_context.json'):
        expected=result.get('recording_evidence',{}).get('source_hashes',{}).get(name)
        if not expected or _sha(attempt/name)!=expected:raise ValueError('Original source hash mismatch: '+name)
    if _sha(attempt/'capture/evidence.jsonl')!=result.get('recording_evidence',{}).get('capture_evidence_sha256'):
        raise ValueError('Capture evidence hash mismatch')
    receipts={}
    for name in CAMERAS:
        receipts[name]=media_auditor(attempt/name,len(mapping),mapping_sha256=_sha(attempt/'video_frames.jsonl'))
        if not receipts[name].get('passed',True):raise ValueError('Source camera decode failed: '+name)
    return {'format':'worker-c10301-source-audit','case_id':case_id,'source_frame_count':len(mapping),
            'sampled_peak_speed_mph':peak,'original_sources_sha256':{name:_sha(attempt/name) for name in CAMERAS},
            'camera_decode_receipts':receipts,'source_integrity_passed':True,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
