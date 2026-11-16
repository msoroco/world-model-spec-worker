"""Original-frame observations for the no-crosswalk alternatives in NRS 484A.450(2).

The law chooses a marked stop line if present, otherwise the first point with a
view of approaching traffic. This module measures source ordering; it does not
assign legal sufficiency to a marked line or a sampled visibility proxy.
"""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon
from crosswalk_stop_measurements import _number, _points, _rows


def _source(root,name,hashes):
    path=root/name
    if not path.is_file():raise ValueError('Missing original source: '+name)
    hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def analyze(root):
    root=Path(root);hashes={}
    ctx=json.loads(_source(root,'approach_context.json',hashes).read_text())
    rows=_rows(_source(root,'stop_history.jsonl',hashes))
    frames=_rows(_source(root,'video_frames.jsonl',hashes))
    if ctx.get('near_side_crosswalk_exists') is not False or not ctx.get('crosswalk_absence_source'):
        raise ValueError('No-crosswalk branch requires sourced crosswalk absence')
    for key in ('native_map_id','intersection_id','approach_road_id','approach_lane_id',
                'native_stop_sign_id','sign_governance_source','junction_source'):
        if ctx.get(key) is None:raise ValueError('Missing sourced approach context: '+key)
    if len(rows)<4 or len(rows)!=len(frames):raise ValueError('Incomplete original history')
    forward=ctx.get('approach_forward_xy')
    if not isinstance(forward,list) or len(forward)!=2:raise ValueError('Missing approach direction')
    fx,fy=(_number(v,'approach direction') for v in forward)
    norm=math.hypot(fx,fy)
    if norm==0:raise ValueError('Zero approach direction')
    fx,fy=fx/norm,fy/norm
    junction=Polygon(_points(ctx.get('intersection_polygon_xy_m'),'junction polygon',3))
    if not junction.is_valid or junction.area<=0:raise ValueError('Invalid junction polygon')
    stop_line=ctx.get('stop_line_exists')
    if type(stop_line) is not bool:raise ValueError('Missing marked stop-line disposition')
    if stop_line:
        if not ctx.get('stop_line_marking_source'):raise ValueError('Missing marked stop-line source')
        line=_points(ctx.get('stop_line_segment_xy_m'),'stop line segment',2)
        if len(line)!=2:raise ValueError('Stop line must have two endpoints')
        projection=min(x*fx+y*fy for x,y in line)
        selected='marked_stop_line';sight=None
    else:
        if not ctx.get('sight_observer_source') or not ctx.get('approaching_traffic_source'):
            raise ValueError('Missing visibility observer or traffic source')
        sight=_rows(_source(root,'sight_history.jsonl',hashes))
        if len(sight)!=len(rows):raise ValueError('Incomplete original sight history')
        selected='first_observed_view';projection=None
    first_halt=None;first_reference=None;first_junction=None;first_view=None
    previous=(-1,-math.inf);samples=[]
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid=row.get('frame');t=_number(row.get('time_s'),'time')
        if type(fid) is not int or fid<=previous[0] or t<=previous[1]:raise ValueError('Nonmonotone original history')
        previous=fid,t
        if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=t:
            raise ValueError('Original frame join failed')
        if row.get('stop_sign_id')!=ctx['native_stop_sign_id']:
            raise ValueError('Stop sign identity mismatch')
        if first_reference is None and (row.get('road_id')!=ctx['approach_road_id'] or row.get('lane_id')!=ctx['approach_lane_id']):
            raise ValueError('Approach lane identity mismatch')
        speed=_number(row.get('ego_speed_mps'),'ego speed')
        if speed<0:raise ValueError('Negative ego speed')
        points=_points(row.get('ego_body_vertices_xy_m'),'complete ego body',4)
        body=MultiPoint(points).convex_hull
        in_junction=body.intersects(junction)
        if stop_line:
            before=max(x*fx+y*fy for x,y in points)<projection
            at_reference=not before
        else:
            obs=sight[i]
            if obs.get('frame')!=fid or obs.get('time_s')!=t:raise ValueError('Original sight frame join failed')
            ids=obs.get('visible_approaching_traffic_ids')
            inventory=obs.get('approaching_traffic_ids')
            if (not isinstance(ids,list) or not isinstance(inventory,list) or
                not all(type(v) in (str,int) for v in ids+inventory) or
                not set(ids).issubset(set(inventory))):
                raise ValueError('Missing or inconsistent original approaching-traffic visibility')
            at_reference=bool(ids)
            if at_reference and first_view is None:first_view={'frame':fid,'time_s':t,'visible_ids':ids}
            before=not at_reference
        if i==0 and (at_reference or in_junction):raise ValueError('Missing approach before selected reference')
        if speed==0 and first_halt is None:first_halt={'frame':fid,'time_s':t,'before_reference':before}
        if at_reference and first_reference is None:first_reference={'frame':fid,'time_s':t}
        if in_junction and first_junction is None:first_junction={'frame':fid,'time_s':t}
        samples.append({'frame':fid,'time_s':t,'speed_mps':speed,'body_before_reference':before,'body_in_junction':in_junction})
    if first_reference is None or first_junction is None:raise ValueError('Reference and junction entry must be observed')
    ordered=bool(first_halt and first_halt['time_s']<first_reference['time_s']<first_junction['time_s'] and first_halt['before_reference'])
    return {'format':'worker-stop-reference-observations','selected_reference':selected,
            'source_sha256':hashes,'first_full_halt':first_halt,'first_reference':first_reference,
            'first_observed_view':first_view,'first_intersection_entry':first_junction,
            'halt_before_reference_and_junction_observed':ordered,'samples':samples,
            'sight_limit':'sampled visibility proxy; actual driver view and nearest point unresolved' if not stop_line else None,
            'legal_conclusion':'unresolved'}
