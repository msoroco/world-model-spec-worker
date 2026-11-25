"""Independent source-shaped checks; this does not accept physical evidence."""
import hashlib
import json
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_attempt(attempt, report):
    attempt=Path(attempt)
    report=dict(report)
    if report.get('frame_count')!=600 or report.get('rate_hz')!=20:
        raise ValueError('Original duration or frame rate differs')
    if report.get('right_of_way_verdict')!='unresolved' or report.get('legal_verdict_claimed') is not False:
        raise ValueError('Unsupported legal right-of-way finding')
    if report.get('section_stem_recovered') is not True:
        raise ValueError('Parent section source unreviewed')
    if report.get('backing_frame_count',0)<=0 or report.get('other_moving_frame_count',0)<=0:
        raise ValueError('Backing or moving traffic absent')
    if report.get('simultaneous_backing_and_other_moving_frame_count',0)<=0:
        raise ValueError('No simultaneous backing and moving traffic')
    required=('traffic-context.json','native-motion.jsonl','video_frames.jsonl')
    for name in required:
        if report.get('source_sha256',{}).get(name)!=_sha(attempt/name):
            raise ValueError('Original source hash mismatch: '+name)
    for name in ('overview','approach','reference_corner','driver_reference'):
        source=attempt/(name+'.mkv')
        if report.get('camera_video_sha256',{}).get(name)!=_sha(source):
            raise ValueError('Original camera hash mismatch: '+name)
    return {'source_bindings_passed':True,'physical_acceptance_claimed':False}


def audit_comparison(left,right,left_config,right_config):
    a,b=dict(left),dict(right)
    if a.get('frame_count')!=b.get('frame_count') or a.get('rate_hz')!=b.get('rate_hz'):
        raise ValueError('Comparison capture timing differs')
    fixed=('cell_id','law_id','actor','duration_s','rate_hz','cameras')
    for key in fixed:
        if left_config.get(key)!=right_config.get(key):
            raise ValueError('Comparison fixed condition differs: '+key)
    if left_config.get('case_suffix')==right_config.get('case_suffix'):
        raise ValueError('Comparison timing variable absent')
    for report in (a,b):
        if report.get('right_of_way_verdict')!='unresolved':
            raise ValueError('Comparison cannot assign a legal verdict')
    return {'fixed_conditions_checked':list(fixed),'declared_difference':'backing onset timing',
            'physical_acceptance_claimed':False}
