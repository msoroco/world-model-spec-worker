"""Canonical native output writers. Never repair or rewrite original evidence."""
import json, math
from pathlib import Path
from .common import write

REQUIRED=('measured_values','target_checks','setup_confirmed','behavior_attempted','maneuver_completed','termination_reason','physical_failure_flags','trace_reference','video_references','video_frame_map_reference','recording_description','recording_evidence','realized_observables')

def frame_record(index, frame, time_s, **extra):
    if type(index) is not int or index<0 or type(frame) is not int or isinstance(time_s,bool) or not isinstance(time_s,(int,float)) or not math.isfinite(time_s):raise ValueError('Invalid original frame')
    if set(extra)&{'video_frame','carla_frame','native_frame','time_s'}:raise ValueError('Cannot override original identity')
    return dict(extra,video_frame=index,carla_frame=frame,native_frame=frame,time_s=time_s)

def validate_result(result):
    if not isinstance(result,dict):raise ValueError('Native result must be an object')
    if any(k not in result for k in REQUIRED):raise ValueError('Missing native result field')
    if any(k in result for k in ('legal_verdict','compliant','violating')):raise ValueError('Prohibited legal verdict')
    if not result['target_checks'] or not result['video_references']:raise ValueError('Missing targets or footage')
    for check in result['target_checks']:
        if any(k not in check for k in ('target','requested','measured','method','tolerance','matched','physical_cause_confirmed','cause_evidence')):raise ValueError('Incomplete measured target')
    json.dumps(result,allow_nan=False)
    for key in ('setup_confirmed','behavior_attempted','maneuver_completed'):
        if type(result[key]) is not bool:raise ValueError('Explicit physical status required: '+key)
    return result

def write_result(attempt,result):
    path=Path(attempt)/'result.json'
    if path.exists():raise ValueError('Retain prior result; choose a fresh attempt')
    validate_result(result)
    with path.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return path

class FrameMap:
    """Append original identities once, at capture time, in acquisition order."""
    def __init__(self,path):
        self.stream=Path(path).open('x',buffering=1);self.index=0;self.previous=None
    def append(self,frame,time_s,**extra):
        row=frame_record(self.index,frame,time_s,**extra)
        if self.previous and (frame<=self.previous[0] or time_s<=self.previous[1]):raise ValueError('Original frames/times must increase')
        self.stream.write(json.dumps(row,allow_nan=False)+'\n');self.previous=(frame,time_s);self.index+=1
        return row
    def close(self):self.stream.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
