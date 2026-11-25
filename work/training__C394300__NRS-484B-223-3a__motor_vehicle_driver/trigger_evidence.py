"""Source-hashed 3(a) fallback triggers; synthetic inputs remain synthetic."""
import hashlib
import json
import math
from pathlib import Path

TRIGGERS={
    'fallback1':{'metric':'center_lane_approach_span_m','threshold_m':10.0,
                 'reason':'Need enough measured center-lane approach to classify use before the first turn opportunity.'},
    'fallback2':{'metric':'max_pre_turn_route_error_m','threshold_m':.75,
                 'reason':'Body tracking near the first turn opportunity must preserve which movement occurred.'},
    'fallback3':{'metric':'center_lane_and_body_visible_fraction','threshold':.90,
                 'reason':'The center lane and subject body must be visible at the decisive frames.'}}


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(folder,candidate):
    if candidate not in TRIGGERS:raise ValueError('Unknown fallback')
    folder=Path(folder)
    source=folder/'native_samples.jsonl'
    rows=[json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    frames=[r.get('native_frame') for r in rows]
    if not rows or any(type(f) is not int for f in frames) or frames!=sorted(set(frames)):
        raise ValueError('Missing or unordered Native samples')
    if any(r.get('source_kind') not in ('synthetic_cpu','original_native') for r in rows):
        raise ValueError('Native sample provenance missing')
    if len({r['source_kind'] for r in rows})!=1:
        raise ValueError('Mixed synthetic and original Native rows')
    sources={'native_samples.jsonl':_sha(source)}
    if candidate=='fallback1':
        values=[]
        for r in rows:
            if r.get('native_road_id')==1 and r.get('native_lane_id')==-1:
                xy=r.get('native_center_xy_m')
                if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xy):
                    raise ValueError('Invalid center-lane pose')
                if xy[0]<-10:values.append(float(xy[0]))
        span=max(values)-min(values) if len(values)>1 else 0.0
        metric={'center_lane_approach_span_m':round(span,4)}
        triggered=span<TRIGGERS[candidate]['threshold_m']
    elif candidate=='fallback2':
        values=[]
        for r in rows:
            xy=r.get('native_center_xy_m')
            if not isinstance(xy,list) or len(xy)!=2:raise ValueError('Native center pose missing')
            if -20<=xy[0]<=-8:
                request=r.get('controller_request')
                value=request.get('route_error_m') if isinstance(request,dict) else None
                if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                    raise ValueError('Invalid observed route error')
                values.append(float(value))
        if not values:raise ValueError('No pre-turn tracking observations')
        metric={'max_pre_turn_route_error_m':round(max(values),4)}
        triggered=max(values)>TRIGGERS[candidate]['threshold_m']
    else:
        audit_path=folder/'pixel_visibility_audit.json'
        audit=json.loads(audit_path.read_text())
        if rows[0]['source_kind']=='original_native':
            if audit.get('independent_original_pixel_review') is not True:
                raise ValueError('Independent original pixel review missing')
        elif audit.get('review_scope')!='synthetic_cpu':
            raise ValueError('Synthetic pixel review scope missing')
        if audit.get('source_video_sha256')!=_sha(folder/'overview.mkv'):
            raise ValueError('Pixel audit source hash mismatch')
        flags=audit.get('frames')
        if not isinstance(flags,list) or [r.get('native_frame') for r in flags]!=frames:
            raise ValueError('Pixel audit frame coverage mismatch')
        if any(type(r.get('center_lane_visible')) is not bool or type(r.get('body_visible')) is not bool for r in flags):
            raise ValueError('Invalid original pixel annotation')
        fraction=sum(r['center_lane_visible'] and r['body_visible'] for r in flags)/len(flags)
        metric={'center_lane_and_body_visible_fraction':round(fraction,4)}
        triggered=fraction<TRIGGERS[candidate]['threshold']
        sources.update({'pixel_visibility_audit.json':_sha(audit_path),'overview.mkv':_sha(folder/'overview.mkv')})
    return {'candidate':candidate,'triggered':triggered,'metric':metric,
            'source_hashes':sources,'source_kind':rows[0]['source_kind'],
            'physical_success_claimed':False,'reason':TRIGGERS[candidate]['reason']}
