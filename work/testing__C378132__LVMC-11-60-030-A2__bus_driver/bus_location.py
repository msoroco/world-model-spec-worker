"""Source-bound measurement of the actual bus stop location and loading purpose."""
from pathlib import Path
import hashlib
import json

KINDS = {'site': 'reviewed_bus_loading_site', 'designation': 'bus_loading_designations',
         'route': 'assigned_bus_route', 'identity': 'bus_operator_identity',
         'activity': 'bus_stop_activity_review', 'purpose': 'loading_purpose_review',
         'circumstances': 'stop_circumstances_review', 'native': 'native_bus_frame_ledger'}
PERMITTED = ('bus_stop', 'bus_stand', 'passenger_loading_zone', 'route_origin', 'route_destination')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_bound(root, ref, kind):
    rel = ref.get('path')
    if not isinstance(rel, str) or rel.startswith('/') or '..' in Path(rel).parts:
        raise ValueError('unsafe source path')
    path = (Path(root) / rel).resolve()
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
        raise ValueError('missing source: ' + str(rel))
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


def footprint_location(footprint, polygons):
    if not isinstance(footprint, list) or len(footprint) != 4 or any(
            not isinstance(point, list) or len(point) != 2 for point in footprint):
        raise ValueError('missing bus body footprint')
    full = [name for name, poly in polygons.items() if all(inside(p, poly) for p in footprint)]
    partial = [name for name, poly in polygons.items() if any(inside(p, poly) for p in footprint)]
    if partial and len(full) != 1:
        return 'boundary_overlap'
    if len(full) > 1:
        raise ValueError('bus belongs to multiple designated locations')
    return full[0] if full else 'outside'


def measure(root, refs, *, expected_frames=900, diagnostic=False):
    packets = {key: read_bound(root, refs[key], kind) for key, kind in KINDS.items()}
    if diagnostic:
        if any(packet.get('source_class')!='synthetic_diagnostic' for packet in packets.values()):
            raise ValueError('diagnostic measurement needs only synthetic source packets')
    else:
        for key,packet in packets.items():
            expected='original_native_capture' if key=='native' else 'original_independent_review'
            if packet.get('source_class')!=expected:
                raise ValueError('original source class unverified: '+key)
    site, designation, route = (packets[key] for key in ('site', 'designation', 'route'))
    identity, activity, purpose = (packets[key] for key in ('identity', 'activity', 'purpose'))
    circumstances, native = (packets[key] for key in ('circumstances', 'native'))
    if site.get('cell_id') != 'C378132' or site.get('layout') != 'business_district' or site.get('public_street') is not True:
        raise ValueError('wrong public-street business-district source')
    for key in ('reviewer', 'jurisdiction_source_sha256', 'boundary_source_sha256', 'designation_source_sha256'):
        if not site.get(key):
            raise ValueError('missing independently reviewed site source: ' + key)
    polygons = site.get('location_polygons_xy_m')
    if not isinstance(polygons, dict) or set(polygons) != set(PERMITTED):
        raise ValueError('complete five-location polygon inventory required')
    for name, polygon in polygons.items():
        if not isinstance(polygon, list) or len(polygon) < 4 or any(not isinstance(p, list) or len(p) != 2 for p in polygon):
            raise ValueError('reviewed location polygon missing: ' + name)
    if designation.get('authority') != 'City Traffic Engineer' or designation.get('source_sha256') != site['designation_source_sha256']:
        raise ValueError('official designation source mismatch')
    if set(designation.get('designated_locations', [])) != set(PERMITTED) or not designation.get('signs_reviewed'):
        raise ValueError('stop/stand/zone/route-termini designations unreviewed')
    if route.get('route_id') != identity.get('assigned_route') or not route.get('source_sha256') or not route.get('origin_destination_reviewed'):
        raise ValueError('assigned-route origin and destination unproved')
    if identity.get('bus_id') != native.get('bus_id') or not identity.get('covered_operator') or identity.get('tour_bus') not in (True, False):
        raise ValueError('bus classification or operator identity unproved')
    if not identity.get('bus_class_source_sha256') or not identity.get('operator_source_sha256'):
        raise ValueError('independent bus/operator classification missing')
    if purpose.get('loading_purpose') not in ('passenger', 'baggage', 'cargo_only') or not purpose.get('independent_reviewer'):
        raise ValueError('passenger/baggage purpose review missing')
    if purpose.get('bus_id') != identity['bus_id'] or not purpose.get('source_sha256'):
        raise ValueError('purpose source does not bind bus')
    if circumstances.get('stop_reason') not in ('ordinary', 'emergency') or not circumstances.get('independent_reviewer'):
        raise ValueError('emergency/ordinary circumstance review missing')
    if circumstances.get('bus_id') != identity['bus_id'] or not circumstances.get('source_sha256'):
        raise ValueError('circumstance source does not bind bus')
    frames = native.get('frames')
    if not isinstance(frames, list) or len(frames) != expected_frames:
        raise ValueError('incomplete Native frame ledger')
    for i, row in enumerate(frames):
        if row.get('frame') != i or abs(row.get('time_s', -1) - i/20) > 0.00001:
            raise ValueError('Native frame/time join failed')
        if row.get('bus_id') != identity['bus_id']:
            raise ValueError('bus identity changed in Native ledger')
        if row.get('measured_location') != footprint_location(row.get('bus_footprint_xy_m'), polygons):
            raise ValueError('bus footprint/location measurement differs')
    events = activity.get('events')
    if not isinstance(events, list) or len(events) < 2 or not activity.get('independent_reviewer'):
        raise ValueError('missing independently reviewed stop transitions')
    if events[0].get('event') != 'start' or events[-1].get('event') != 'end':
        raise ValueError('complete stop interval unresolved')
    begin, finish = events[0].get('frame'), events[-1].get('frame')
    if not isinstance(begin, int) or not isinstance(finish, int) or begin < 0 or finish >= expected_frames or finish <= begin:
        raise ValueError('stop interval outside capture')
    if any(frames[i].get('bus_speed_mps', 99) > 0.2 for i in range(begin, finish+1)):
        raise ValueError('bus did not remain stopped during reviewed interval')
    locations = {frames[i]['measured_location'] for i in range(begin, finish+1)}
    if len(locations) != 1:
        raise ValueError('bus crossed a location boundary during stop')
    return {'case_measurement': 'bus_loading_stop_location',
            'location_kind': locations.pop(), 'loading_purpose': purpose['loading_purpose'],
            'stop_reason': circumstances['stop_reason'],
            'bus_class': 'tour' if identity['tour_bus'] else 'regular',
            'interval_frames': [begin, finish], 'observed_duration_s': (finish-begin)/20,
            'source_refs': refs, 'diagnostic_only': bool(diagnostic), 'legal_verdict': None}
