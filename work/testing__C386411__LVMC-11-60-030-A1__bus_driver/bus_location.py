"""Source-bound bus position and conduct measurement, without a legal verdict."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(root: Path, ref: dict, kind: str) -> dict:
    rel = ref.get('path')
    if not isinstance(rel, str) or rel.startswith('/') or '..' in Path(rel).parts:
        raise ValueError('unsafe source path')
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('missing source: ' + rel)
    if sha(path) != ref.get('sha256'):
        raise ValueError('changed source: ' + rel)
    value = json.loads(path.read_text())
    if value.get('kind') != kind:
        raise ValueError('wrong source kind: ' + kind)
    return value


def inside(point, polygon):
    x, y = point
    hit = False
    for index in range(len(polygon)):
        x1, y1 = polygon[index-1]
        x2, y2 = polygon[index]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            hit = not hit
    return hit


def boundary_relation(footprint, polygon):
    """Classify a complete bus body; reject any contact with a stop edge."""
    statuses = [inside(point, polygon) for point in footprint]
    if all(statuses):
        return 'inside'

    def orientation(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

    def crosses(a, b, c, d):
        ab_c, ab_d = orientation(a,b,c), orientation(a,b,d)
        cd_a, cd_b = orientation(c,d,a), orientation(c,d,b)
        return ((ab_c == 0 and min(a[0],b[0]) <= c[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= c[1] <= max(a[1],b[1]))
                or (ab_d == 0 and min(a[0],b[0]) <= d[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= d[1] <= max(a[1],b[1]))
                or (cd_a == 0 and min(c[0],d[0]) <= a[0] <= max(c[0],d[0]) and min(c[1],d[1]) <= a[1] <= max(c[1],d[1]))
                or (cd_b == 0 and min(c[0],d[0]) <= b[0] <= max(c[0],d[0]) and min(c[1],d[1]) <= b[1] <= max(c[1],d[1]))
                or ((ab_c > 0) != (ab_d > 0) and (cd_a > 0) != (cd_b > 0)))

    if any(statuses):
        return 'mixed'
    for i in range(len(footprint)):
        for j in range(len(polygon)):
            if crosses(footprint[i-1], footprint[i], polygon[j-1], polygon[j]):
                return 'mixed'
    if any(inside(point, footprint) for point in polygon):
        return 'mixed'
    return 'outside'


def measure(root: Path, refs: dict, *, expected_frames: int = 900, diagnostic: bool = False) -> dict:
    kinds = {'site':'reviewed_bus_stop_site', 'designation':'bus_stop_designation',
             'identity':'bus_operator_identity', 'activity':'bus_activity_review',
             'native':'native_bus_frame_ledger'}
    packets = {key: read_bound(root, refs[key], kind) for key, kind in kinds.items()}
    if any(p.get('source_class') == 'synthetic_diagnostic' for p in packets.values()) and not diagnostic:
        raise ValueError('synthetic diagnostic source cannot establish original measurement')
    site, designation, identity, activity, native = (packets[key] for key in kinds)
    if site.get('cell_id') != 'C386411' or site.get('layout') != 'one_way_road' or site.get('stop_kind') != 'bus_stop':
        raise ValueError('wrong original site or stop kind')
    if site.get('public_street') is not True or not site.get('jurisdiction_source_sha256'):
        raise ValueError('public-street jurisdiction unproved')
    if not site.get('reviewer') or not site.get('boundary_source_sha256') or not site.get('designation_source_sha256'):
        raise ValueError('missing independently reviewed stop source')
    polygon = site.get('stop_polygon_xy_m')
    if not isinstance(polygon, list) or len(polygon) < 4 or any(not isinstance(p,list) or len(p)!=2 for p in polygon):
        raise ValueError('reviewed stop polygon missing')
    if designation.get('stop_id') != site.get('stop_id') or designation.get('authority') != 'City Traffic Engineer':
        raise ValueError('designation does not bind stop and authority')
    if designation.get('source_sha256') != site['designation_source_sha256'] or designation.get('signed') is not True:
        raise ValueError('official signed stop designation unproved')
    if not designation.get('route_termini_reviewed') or not designation.get('other_permitted_locations_reviewed'):
        raise ValueError('other permitted origin, destination and stand locations unreviewed')
    if identity.get('bus_id') != native.get('bus_id') or identity.get('tour_bus') is not False or not identity.get('covered_operator'):
        raise ValueError('covered non-tour bus/operator identity unproved')
    if not identity.get('assigned_route') or not identity.get('route_source_sha256'):
        raise ValueError('assigned bus route unproved')
    frames = native.get('frames')
    if not isinstance(frames,list) or len(frames)!=expected_frames:
        raise ValueError('incomplete Native frame ledger')
    for i,row in enumerate(frames):
        if row.get('frame') != i or abs(row.get('time_s',-1)-i/20) > 0.00001:
            raise ValueError('Native frame/time join failed')
        if row.get('bus_id') != identity['bus_id']:
            raise ValueError('bus identity changed in Native ledger')
        footprint = row.get('bus_footprint_xy_m')
        if not isinstance(footprint,list) or len(footprint)!=4 or any(not isinstance(point,list) or len(point)!=2 for point in footprint):
            raise ValueError('missing bus body footprint')
        actual_inside = all(inside(point,polygon) for point in footprint)
        if row.get('inside_stop_boundary') is not actual_inside:
            raise ValueError('bus body/stop boundary measurement differs')
    events = activity.get('events')
    if not isinstance(events,list) or len(events)<2 or not activity.get('independent_reviewer'):
        raise ValueError('missing independently reviewed activity transitions')
    conduct = activity.get('conduct')
    if conduct not in ('stand','park') or events[0].get('event')!='start' or events[-1].get('event')!='end':
        raise ValueError('standing or parking interval unresolved')
    begin,finish = events[0].get('frame'),events[-1].get('frame')
    if not isinstance(begin,int) or not isinstance(finish,int) or begin<0 or finish>=expected_frames or finish<=begin:
        raise ValueError('activity interval outside capture')
    if any(e.get('event') in ('load','unload','merchandise') for e in events):
        raise ValueError('activity changed; independent segmentation required')
    observed=[boundary_relation(frames[i]['bus_footprint_xy_m'],polygon) for i in range(begin,finish+1)]
    if 'mixed' in observed or len(set(observed)) != 1:
        raise ValueError('bus body crossed or straddled stop boundary during standing or parking')
    relation=observed[0]
    if relation=='outside' and not all(frames[i].get('outside_other_permitted_location') is True for i in range(begin,finish+1)):
        raise ValueError('outside stop may be origin, destination or bus stand')
    return {'case_measurement':'bus_stand_park_designated_location','site_stop_id':site['stop_id'],
            'conduct':conduct,'location_relation':relation,'interval_frames':[begin,finish],
            'observed_duration_s':(finish-begin)/20,'source_refs':refs,
            'diagnostic_only':bool(diagnostic),'legal_verdict':None}
