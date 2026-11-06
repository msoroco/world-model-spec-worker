"""Source-bound CPU geometry test for time-scoped alley/facility crossing."""
import hashlib
import json
import math
from pathlib import Path

from measure_facility import overlap_area, rectangle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'alley-transition-sources.json').read_text())
    if manifest.get('format')!='c10052-alley-transition-sources-v1':
        raise ValueError('Unknown alley transition manifest')
    source_kind=manifest.get('source_kind')
    if source_kind not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Alley transition provenance unverified')
    expected=manifest.get('sha256',{})
    if set(expected)!={'native_samples.jsonl','road_geometry.json'}:
        raise ValueError('Alley transition sources incomplete')
    for name,digest in expected.items():
        if sha(folder/name)!=digest:
            raise ValueError('Alley transition source hash differs: '+name)
    geometry=json.loads((folder/'road_geometry.json').read_text())
    facility=rectangle(geometry.get('bicycle_facility_native_xy_bounds_m'),'facility')
    alley=rectangle(geometry.get('alley_entrance_native_xy_bounds_m'),'alley entrance')
    samples=[json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines()
             if line.strip()]
    if len(samples)!=480:
        raise ValueError('Alley transition needs 480 frames')
    facility_area=[];alley_area=[];moving=[]
    for i,row in enumerate(samples):
        if source_kind=='synthetic_cpu_fixture' and row.get('synthetic_diagnostic') is not True:
            raise ValueError('Alley transition fixture provenance differs')
        if source_kind=='original_native' and row.get('synthetic_diagnostic') is True:
            raise ValueError('Alley transition provenance unverified: synthetic row labeled original')
        if source_kind=='synthetic_cpu_fixture':
            if row.get('native_frame')!=100+i or abs(row.get('time_s',-1)-(i+1)/20)>1e-6:
                raise ValueError('Alley transition frame/time differs')
        elif (type(row.get('native_frame')) is not int or
              row['native_frame']!=samples[0]['native_frame']+i or
              type(row.get('time_s')) not in (int,float) or
              abs(row['time_s']-(samples[0]['time_s']+i/20))>1e-3):
            raise ValueError('Original alley transition frame/time differs')
        center=row.get('native_center_xy_m')
        body=row.get('native_body_xy_m')
        speed=row.get('speed_mps')
        if (not isinstance(center,list) or len(center)!=2 or
            not all(type(v) in (int,float) and math.isfinite(v) for v in center) or
            type(speed) not in (int,float) or not math.isfinite(speed) or speed<0):
            raise ValueError('Alley transition pose invalid')
        if (abs(sum(v[0] for v in body)/4-center[0])>1e-6 or
            abs(sum(v[1] for v in body)/4-center[1])>1e-6):
            raise ValueError('Alley transition body/center differs')
        facility_area.append(overlap_area(body,facility))
        alley_area.append(overlap_area(body,alley))
        moving.append(speed>.1)
    first_facility=next((i for i in range(1,480)
        if moving[i] and facility_area[i-1]<=.01 and facility_area[i]>.01),None)
    first_alley=next((i for i in range(480) if moving[i] and alley_area[i]>.01),None)
    simultaneous=sum(moving[i] and facility_area[i]>.01 and alley_area[i]>.01
                     for i in range(480))
    time_gap=None if first_facility is None or first_alley is None else round(
        samples[first_alley]['time_s']-samples[first_facility]['time_s'],6)
    candidate=(first_facility is not None and first_alley is not None and
        0<=time_gap<=2 and simultaneous>0 and
        any(row['native_center_xy_m'][1]<alley[3] for row in samples[first_alley:]))
    return {'format':'c10052-synthetic-alley-transition-v1',
        'source_sha256':expected,'source_kind':source_kind,
        'first_facility_entry_native_frame':None if first_facility is None else samples[first_facility]['native_frame'],
        'first_alley_footprint_native_frame':None if first_alley is None else samples[first_alley]['native_frame'],
        'facility_to_alley_gap_s':time_gap,
        'simultaneous_moving_overlap_frames':simultaneous,
        'time_bounded_geometry_candidate':candidate,
        'native_route_identity_verified':False,
        'facility_designation_verified':False,
        'statutory_exception_observed':'unresolved',
        'legal_verdict_claimed':False,'accepted':False}
