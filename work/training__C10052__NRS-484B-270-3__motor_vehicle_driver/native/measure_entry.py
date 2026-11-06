"""Measure a moving full-body crossing into an authored bicycle facility."""
import hashlib
import json
import math
from pathlib import Path

from measure_facility import overlap_area, rectangle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(folder):
    folder=Path(folder)
    source=json.loads((folder/'entry-sources.json').read_text())
    if source.get('format')!='c10052-entry-sources-v1':
        raise ValueError('Unknown entry source manifest')
    kind=source.get('source_kind')
    if kind not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Unknown entry source provenance')
    if set(source.get('sha256',{}))!={'native_samples.jsonl','road_geometry.json'}:
        raise ValueError('Incomplete entry source hashes')
    for name,expected in source['sha256'].items():
        path=folder/name
        if not path.is_file() or sha(path)!=expected:
            raise ValueError('Entry source hash differs: '+name)
    geometry=json.loads((folder/'road_geometry.json').read_text())
    facility=rectangle(geometry.get('bicycle_facility_native_xy_bounds_m'),'bicycle facility')
    alley=rectangle(geometry.get('alley_entrance_native_xy_bounds_m'),'alley entrance')
    samples=[json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines()
             if line.strip()]
    if len(samples)!=480:
        raise ValueError('Entry source needs 480 frames')
    frames=[];times=[];areas=[];moving=[];lane_ids=[];alley_gaps=[]
    for sample in samples:
        frame,time=sample.get('native_frame'),sample.get('time_s')
        xy=sample.get('native_center_xy_m')
        speed=sample.get('speed_mps')
        if (type(frame) is not int or not finite(time) or
            not isinstance(xy,list) or len(xy)!=2 or not all(finite(v) for v in xy) or
            not finite(speed) or speed<0):
            raise ValueError('Invalid Native entry sample')
        if frames and (frame<=frames[-1] or time<=times[-1] or
                       abs(time-times[-1]-.05)>.002):
            raise ValueError('Entry frame/time order differs')
        if sample.get('native_road_id')!=geometry.get('road_id'):
            raise ValueError('Entry road identity differs')
        lane=sample.get('native_lane_id')
        if lane not in (geometry.get('driving_lane_id'),geometry.get('bicycle_lane_id')):
            raise ValueError('Entry lane identity differs')
        vertices=sample.get('native_body_xy_m')
        area=overlap_area(vertices,facility)
        xs=[vertex[0] for vertex in vertices]
        ys=[vertex[1] for vertex in vertices]
        gap_x=max(alley[0]-max(xs),min(xs)-alley[2],0)
        gap_y=max(alley[1]-max(ys),min(ys)-alley[3],0)
        alley_gaps.append(math.hypot(gap_x,gap_y))
        if (abs(sum(vertex[0] for vertex in vertices)/4-xy[0])>1e-4 or
            abs(sum(vertex[1] for vertex in vertices)/4-xy[1])>1e-4):
            raise ValueError('Entry body and center differ')
        if kind=='original_native' and sample.get('synthetic_diagnostic'):
            raise ValueError('Synthetic entry samples cannot be original Native')
        frames.append(frame);times.append(time);areas.append(area)
        moving.append(speed>.1);lane_ids.append(lane)
    first=next((i for i in range(1,len(samples))
                if areas[i-1]<=.01 and areas[i]>.01 and moving[i]),None)
    return {'format':'c10052-moving-entry-measurement-v1',
        'source_kind':kind,'source_sha256':source['sha256'],
        'original_frames':len(samples),
        'moving_entry_measured':first is not None,
        'first_moving_entry_native_frame':None if first is None else frames[first],
        'first_moving_entry_time_s':None if first is None else times[first],
        'first_moving_entry_overlap_m2':None if first is None else round(areas[first],6),
        'moving_occupied_frames':sum(flag and area>.01 for flag,area in zip(moving,areas)),
        'maximum_moving_overlap_m2':round(max(
            (area for flag,area in zip(moving,areas) if flag),default=0),6),
        'first_entry_alley_footprint_gap_m':None if first is None else round(alley_gaps[first],6),
        'minimum_moving_facility_alley_footprint_gap_m':round(min(
            (gap for flag,area,gap in zip(moving,areas,alley_gaps)
             if flag and area>.01),default=math.inf),6) if any(
            flag and area>.01 for flag,area in zip(moving,areas)) else None,
        'moving_facility_alley_footprint_overlap_frames':sum(
            flag and area>.01 and gap<=1e-6
            for flag,area,gap in zip(moving,areas,alley_gaps)),
        'driving_lane_observed':geometry.get('driving_lane_id') in lane_ids,
        'bicycle_lane_observed':geometry.get('bicycle_lane_id') in lane_ids,
        'facility_designation_verified':geometry.get('native_facility_design_verified') is True,
        'exception_a_observed':'unresolved',
        'legal_verdict_claimed':False,'accepted':False}
