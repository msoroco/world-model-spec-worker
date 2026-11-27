"""Source-bound measurement for LVMC 11.48.060, without legal classification."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

KINDS = ('none', 'pick_up', 'delivery', 'essential_use')
STREETS = ('truck_route', 'non_truck')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_xy(value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('A route position needs two coordinates')
    x, y = float(value[0]), float(value[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError('A route position must be finite')
    return x, y


def load_review(path: Path, source_root: Path, case_id: str, diagnostic: bool = False) -> dict:
    """Require reviewed original route status before Native mutation."""
    packet = json.loads(path.read_text())
    if packet.get('format') != 'worker-reviewed-truck-route-site' or packet.get('case_id') != case_id:
        raise ValueError('Route review identity differs')
    if bool(packet.get('diagnostic_fixture')) != diagnostic:
        raise ValueError('Synthetic route source cannot become original evidence')
    provenance = packet.get('source_provenance', {})
    if not diagnostic and (provenance.get('kind') != 'original_reviewed_site'
            or not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('Original route needs independent reviewer and citation')
    source_files = provenance.get('files', [])
    if not source_files:
        raise ValueError('Authoritative source files missing')
    for source in source_files:
        if not isinstance(source, dict) or not source.get('path') or not source.get('sha256'):
            raise ValueError('Unversioned original route source')
        item = (source_root / source['path']).resolve()
        if source_root.resolve() not in item.parents or not item.is_file() or sha(item) != source['sha256']:
            raise ValueError('Original route source missing or hash differs')
    site = packet.get('site', {})
    if site.get('municipal_jurisdiction_reviewed') is not True:
        raise ValueError('Municipal jurisdiction unreviewed')
    if site.get('chapter_scope_reviewed') is not True:
        raise ValueError('Chapter actor and vehicle scope unreviewed')
    hashes = {row['sha256'] for row in source_files}
    routes = site.get('truck_routes', {})
    if not all(isinstance(routes.get(key), dict) and routes[key].get('designation_source_sha256')
               and routes[key].get('road_id') for key in ('origin', 'destination')):
        raise ValueError('Both authoritative truck route designations required')
    if any(type(routes[key]['road_id']) is not int or routes[key]['designation_source_sha256'] not in hashes for key in ('origin', 'destination')):
        raise ValueError('Original truck-route identity or cited designation source invalid')
    if routes['origin']['road_id'] == routes['destination']['road_id']:
        raise ValueError('Distinct truck routes required')
    street = site.get('intervening_street', {})
    if street.get('designation') not in STREETS or not street.get('road_id') or not street.get('designation_source_sha256'):
        raise ValueError('Intervening street designation source missing')
    if type(street['road_id']) is not int or street['designation_source_sha256'] not in hashes:
        raise ValueError('Original connector identity or cited designation source invalid')
    if site.get('governing_controls_reviewed') is not True:
        raise ValueError('Route controls unreviewed')
    itinerary = packet.get('itinerary', {})
    if itinerary.get('route_use') not in ('through', 'local'):
        raise ValueError('Route-use target missing')
    waypoints = itinerary.get('waypoints_xy_m', [])
    if len(waypoints) < 3:
        raise ValueError('Original route needs at least three waypoints')
    for point in waypoints:
        finite_xy(point)
    if not itinerary.get('origin_on_truck_route') or not itinerary.get('entered_intervening_street'):
        raise ValueError('Route origin and intervening street missing')
    if itinerary['route_use'] == 'through' and not itinerary.get('destination_on_truck_route'):
        raise ValueError('Through route needs destination truck route')
    if itinerary['route_use'] == 'local' and (itinerary.get('destination_on_truck_route') or not itinerary.get('local_destination_reviewed')):
        raise ValueError('Local control needs reviewed local endpoint')
    purpose = packet.get('enroute_purpose', {})
    if purpose.get('kind') not in KINDS:
        raise ValueError('Unknown enroute purpose')
    if purpose['kind'] != 'none' and (not purpose.get('required_enroute_reviewed')
            or not purpose.get('premises_source_sha256') or not purpose.get('activity_source_sha256')):
        raise ValueError('Exception needs independently reviewed necessity, premises and activity')
    if purpose['kind'] != 'none' and (purpose['premises_source_sha256'] not in hashes or purpose['activity_source_sha256'] not in hashes):
        raise ValueError('Original enroute premises or activity source not cited')
    if purpose['kind'] == 'none' and purpose.get('required_enroute_reviewed'):
        raise ValueError('No-purpose control cannot assert an exception')
    if purpose['kind'] != 'none' and not diagnostic:
        protocol = packet.get('activity_protocol', {})
        if (protocol.get('kind') != purpose['kind'] or not protocol.get('reviewed')
                or not protocol.get('source_sha256') or not protocol.get('prop_blueprint')
                or not protocol['prop_blueprint'].startswith('static.prop.')
                or len(protocol.get('premises_xyz_m', [])) != 3
                or protocol.get('source_sha256') not in {row['sha256'] for row in source_files}):
            raise ValueError('Original required-enroute activity construction missing')
        for value in protocol['premises_xyz_m']:
            if not math.isfinite(float(value)):
                raise ValueError('Original premises position invalid')
    return packet


def measure(source: Path) -> dict:
    packet = json.loads(source.read_text())
    case_id = packet.get('case_id')
    frames = packet.get('frames', [])
    if not case_id or len(frames) < 3 or packet.get('fps') != 20:
        raise ValueError('Original 20 Hz route frames missing')
    seen = []
    prior_frame = -1
    prior_time = -1.0
    for row in frames:
        frame, time_s = row.get('frame'), row.get('time_s')
        if not isinstance(frame, int) or frame <= prior_frame or not isinstance(time_s, (int, float)) or time_s <= prior_time:
            raise ValueError('Nonmonotonic original route frame/time')
        if not math.isfinite(time_s) or not isinstance(row.get('ego_actor_id'), int):
            raise ValueError('Original route identity/time invalid')
        finite_xy(row.get('position_xy_m'))
        if row.get('road_id') is None or row.get('street_designation') not in STREETS:
            raise ValueError('Original road identity/status missing')
        seen.append(row['road_id'])
        prior_frame, prior_time = frame, time_s
    site = packet.get('site', {})
    routes = site.get('truck_routes', {})
    street = site.get('intervening_street', {})
    origin = routes.get('origin', {}).get('road_id')
    middle = street.get('road_id')
    destination = routes.get('destination', {}).get('road_id')
    if not origin or not middle or not destination or origin not in seen or middle not in seen:
        raise ValueError('Original origin and intervening road samples missing')
    first_middle = seen.index(middle)
    if seen.index(origin) >= first_middle:
        raise ValueError('Origin must precede connecting road')
    complete = destination in seen[first_middle + 1:]
    if packet.get('itinerary', {}).get('route_use') == 'through' and not complete:
        raise ValueError('Original through passage is incomplete')
    if packet.get('itinerary', {}).get('route_use') == 'local' and complete:
        raise ValueError('Local control unexpectedly reaches destination truck route')
    if not any(row.get('road_id') == middle and row.get('street_designation') == street.get('designation') for row in frames):
        raise ValueError('Connecting road designation not observed')
    purpose = packet.get('enroute_purpose', {})
    kind = purpose.get('kind')
    activities = [row for row in frames if row.get('activity_kind') == kind and row.get('road_id') == middle]
    if kind != 'none' and (not activities or not purpose.get('required_enroute_reviewed')):
        raise ValueError('Required enroute activity not source-observed')
    if kind != 'none' and packet.get('diagnostic_fixture') is False and any(
            type(row.get('activity_prop_actor_id')) is not int or
            row.get('observation_source') != 'original_native_snapshot' for row in activities):
        raise ValueError('Original activity prop readback missing')
    return {'origin_truck_route_observed': True, 'intervening_street_observed': True,
        'destination_truck_route_observed': complete, 'intervening_designation': street['designation'],
        'enroute_purpose_kind': kind, 'enroute_activity_observed': bool(activities),
        'required_enroute_reviewed': bool(purpose.get('required_enroute_reviewed')),
        'sample_count': len(frames), 'first_native_frame': frames[0]['frame'],
        'last_native_frame': frames[-1]['frame']}
