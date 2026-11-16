"""Measure original pedestrian footprints in the direction-relative crosswalk halves.

This reports geometry and source status, never a practicability or legal verdict.
"""
import hashlib
import json
import math
from pathlib import Path

RATE_HZ = 20
FRAMES = 240


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vec(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing original '+name)
    out = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in out):
        raise ValueError('Nonfinite original '+name)
    return out


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    for path in (samples_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required source: '+path.name)
    context = json.loads(context_path.read_text())
    if context.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Unrecognized crosswalk context provenance')
    if not context.get('crosswalk_id') or not isinstance(context.get('practicability_facts'), list):
        raise ValueError('Missing crosswalk identity or practicability source fields')
    if context['source_kind'] == 'native_observation' and (
        not context.get('native_map_sha256') or type(context.get('observed_frame_count')) is not int
    ):
        raise ValueError('Native crosswalk context lacks map/frame provenance')
    center = vec(context.get('crosswalk_center_xy_m'), 'crosswalk center')
    forward = vec(context.get('crosswalk_passage_forward_xy'), 'crosswalk passage direction')
    if abs(math.hypot(*forward)-1) > .001:
        raise ValueError('Crosswalk passage direction must be unit length')
    length, width = context.get('crosswalk_length_m'), context.get('crosswalk_width_m')
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (length, width)):
        raise ValueError('Invalid original crosswalk dimensions')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 12-second original crossing source required')
    if context['source_kind'] == 'native_observation' and context['observed_frame_count'] != len(rows):
        raise ValueError('Native crosswalk frame count differs from samples')
    frames, times, x_positions, inside, classifications = [], [], [], [], []
    right = (forward[1], -forward[0])
    for row in rows:
        frame, t = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or frame < 0 or type(t) not in (int, float) or not math.isfinite(t):
            raise ValueError('Invalid original frame/time')
        if frames and (frame != frames[-1]+1 or abs(t-times[-1]-1/RATE_HZ) > .002):
            raise ValueError('Original crosswalk frame/time order or rate invalid')
        if row.get('crosswalk_id') != context['crosswalk_id']:
            raise ValueError('Original crosswalk identity differs')
        pose = vec(row.get('pedestrian_xy_m'), 'pedestrian position')
        heading = vec(row.get('pedestrian_forward_xy'), 'pedestrian heading')
        if abs(math.hypot(*heading)-1) > .01 or sum(a*b for a,b in zip(heading,forward)) < .98:
            raise ValueError('Original pedestrian heading differs from passage direction')
        speed = row.get('speed_mps')
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed < .2:
            raise ValueError('Pedestrian must be moving through the crosswalk')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(body,list) or len(body) != 4:
            raise ValueError('Missing original pedestrian footprint')
        points = [vec(p,'pedestrian footprint') for p in body]
        if len({(round(x,6),round(y,6)) for x,y in points}) != 4:
            raise ValueError('Degenerate original pedestrian footprint')
        centroid = (sum(p[0] for p in points)/4, sum(p[1] for p in points)/4)
        if math.dist(centroid,pose) > .05:
            raise ValueError('Original footprint does not match pedestrian pose')
        def projections(p):
            delta = (p[0]-center[0], p[1]-center[1])
            return sum(a*b for a,b in zip(delta,forward)), sum(a*b for a,b in zip(delta,right))
        longitudinal, lateral = projections(pose)
        footprints = [projections(p) for p in points]
        if all(abs(u) <= length/2+1e-6 and abs(v) <= width/2+1e-6 for u,v in footprints):
            inside.append(frame)
            if all(v > .01 for _,v in footprints):
                classifications.append('right')
            elif all(v < -.01 for _,v in footprints):
                classifications.append('left')
            else:
                classifications.append('center_or_straddling')
        frames.append(frame); times.append(t); x_positions.append(longitudinal)
    if len(inside) < RATE_HZ*3 or min(x_positions) > -length/2 or max(x_positions) < length/2:
        raise ValueError('Original pedestrian did not traverse the full crosswalk')
    if x_positions[-1] <= x_positions[0] or any(b < a-.02 for a,b in zip(x_positions,x_positions[1:])):
        raise ValueError('Original crosswalk passage is not forward')
    counts = {label:classifications.count(label) for label in ('right','left','center_or_straddling')}
    dominant = max(counts,key=counts.get)
    if counts[dominant] != len(inside):
        dominant = 'mixed'
    return {
        'format':'c10316-crosswalk-half-observation-v1',
        'source_sha256':{samples_path.name:sha(samples_path),context_path.name:sha(context_path)},
        'original_frames':len(rows),'crosswalk_frames':len(inside),
        'crosswalk_first_frame':inside[0],'crosswalk_last_frame':inside[-1],
        'crosswalk_half_counts':counts,'observed_half':dominant,
        'passage_duration_s':round(len(rows)/RATE_HZ,3),
        'context_status':('native_observed_limited' if context['source_kind']=='native_observation'
                          else 'requested_not_observed'),
        'practicability_verified':False,'legal_verdict_claimed':False}
