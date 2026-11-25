"""Read fallback triggers from retained attempt sources; never certify CARLA behavior.

The pixel audit is an independent per-frame annotation. This module verifies
its coverage and source hashes; an annotation is not a substitute for looking
at original pixels during the later GPU review.
"""
import hashlib
import json
import math
from pathlib import Path

from engineering import TRIGGERS, trigger
from measure_after_turn import measure


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    if not path.is_file():
        raise ValueError('Missing original trigger source: '+path.name)
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty original trigger source: '+path.name)
    return rows


def _number(value,name,low=0,high=math.inf):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Invalid original trigger observation: '+name)
    return float(value)


def _coordinate(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Invalid original trigger coordinate: '+name)
    return float(value)


def evaluate(attempt,candidate):
    """Return a source-hashed measured decision for one fallback candidate."""
    if candidate not in TRIGGERS:
        raise ValueError('Unknown fallback trigger')
    folder=Path(attempt)
    samples=folder/'native_samples.jsonl'
    geometry=folder/'road_geometry.json'
    rows=_rows(samples)
    frame_ids=[row.get('native_frame') for row in rows]
    if any(type(frame) is not int for frame in frame_ids) or frame_ids!=sorted(set(frame_ids)):
        raise ValueError('Original Native frame order invalid')
    metrics={};sources={'native_samples.jsonl':_sha(samples)}
    if candidate in ('fallback1','fallback2'):
        if not geometry.is_file():
            raise ValueError('Missing original trigger source: road_geometry.json')
        g=json.loads(geometry.read_text())
        measured=measure(samples,geometry)
        completion=measured['turn_completion_frame_bracket'][1]
        premerge=measured['merge_onset_frame_bracket'][0]
        sources['road_geometry.json']=_sha(geometry)
        if candidate=='fallback1':
            inbound=g.get('inbound_road_id')
            bounds=g.get('inbound_lane_native_xy_bounds_m')
            if type(inbound) is not int or not isinstance(bounds,list) or len(bounds)!=4:
                raise ValueError('Original inbound Native lane survey missing')
            x0,y0,x1,y1=(_coordinate(v,'inbound lane bound') for v in bounds)
            if not x0<x1 or not y0<y1:
                raise ValueError('Original inbound Native lane bounds invalid')
            inbound_rows=[row for row in rows if row.get('native_road_id')==inbound and row['native_frame']<completion]
            if not inbound_rows:
                raise ValueError('Original inbound Native body samples missing')
            contained=0
            for row in inbound_rows:
                body=row.get('native_body_xy_m')
                if not isinstance(body,list) or len(body)!=4:
                    raise ValueError('Original inbound Native body missing')
                points=[tuple(_coordinate(v,'body coordinate') for v in point)
                        for point in body if isinstance(point,list) and len(point)==2]
                if len(points)!=4:
                    raise ValueError('Original inbound Native body invalid')
                contained+=all(x0<=x<=x1 and y0<=y<=y1 for x,y in points)
            completion_row=next(row for row in rows if row['native_frame']==completion)
            start=_number(inbound_rows[0].get('time_s'),'inbound start time')
            finish=_number(completion_row.get('time_s'),'turn completion time')
            if finish<=start:
                raise ValueError('Original turn time order invalid')
            metrics={'inbound_body_containment_fraction':contained/len(inbound_rows),
                     'turn_completion_time_s':finish-start,
                     'inbound_sample_count':len(inbound_rows)}
        else:
            selected=[row for row in rows if row['native_frame']<=premerge]
            errors=[]
            for row in selected:
                request=row.get('controller_request')
                if not isinstance(request,dict):
                    raise ValueError('Original controller request missing')
                errors.append(_number(request.get('route_error_m'),'route_error_m'))
            metrics={'max_premerge_route_error_m':max(errors),'premerge_sample_count':len(errors)}
    else:
        path=folder/'pixel_visibility_audit.json'
        if not path.is_file():
            raise ValueError('Missing original trigger source: pixel_visibility_audit.json')
        audit=json.loads(path.read_text())
        names=('overview','approach','reference_corner','driver_reference')
        videos=audit.get('source_video_sha256')
        if audit.get('independent_original_pixel_review') is not True or not isinstance(videos,dict) or set(videos)!=set(names):
            raise ValueError('Independent original-pixel audit incomplete')
        for name in names:
            video=folder/(name+'.mkv')
            if not video.is_file() or videos[name]!=_sha(video):
                raise ValueError('Original pixel video hash differs: '+name)
            sources[name+'.mkv']=videos[name]
        flags=audit.get('frames')
        if not isinstance(flags,list) or len(flags)!=len(rows):
            raise ValueError('Original pixel frame coverage incomplete')
        visible=0
        for row,flag in zip(rows,flags):
            if not isinstance(flag,dict) or flag.get('native_frame')!=row['native_frame'] or \
                    type(flag.get('marking_visible')) is not bool or type(flag.get('body_visible')) is not bool:
                raise ValueError('Original pixel frame annotation invalid')
            visible+=flag['marking_visible'] and flag['body_visible']
        metrics={'marking_and_body_visible_fraction':visible/len(rows),'reviewed_frame_count':len(rows)}
        sources['pixel_visibility_audit.json']=_sha(path)
    evidence={'source':TRIGGERS[candidate]['source'],**metrics}
    return {'candidate_id':candidate,'triggered':trigger(candidate,evidence),
            'metric':metrics,'source_hashes':sources,'scope':'saved original-source trigger evaluation; physical review pending'}
