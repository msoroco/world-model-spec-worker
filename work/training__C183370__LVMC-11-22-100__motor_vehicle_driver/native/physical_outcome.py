"""Classify sampled route completion separately from statutory acceptance."""
import hashlib
import json

from shapely.geometry import MultiPoint, Polygon

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def check_lifecycle(events, native_exit_code):
    if events != EVENTS or native_exit_code != 0:
        raise ValueError('Saved processing requires closed Native ownership')
    return {'events': events, 'exit_code': 0,
            'original_owner_release_verified': False, 'cpu_fixture_mock': True}


def classify(rows, pavement_polygon_xy_m, requested_contact, *,
             provenance_kind='synthetic_fixture', diagnostic_fixture=True):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Missing sampled Native actor rows')
    if requested_contact not in (True, False):
        raise ValueError('Requested contact must be explicit')
    polygon = Polygon(pavement_polygon_xy_m)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Surveyed pavement polygon invalid')
    sources = {'sampled_actor_rows_sha256': hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'surveyed_polygon_sha256': hashlib.sha256(
            json.dumps(pavement_polygon_xy_m, separators=(',', ':')).encode()).hexdigest()}
    complete_source = len(rows) == 600 and all(
        row.get('frame') == index and
        abs(row.get('time_s', -1) - (index + 1) / 20) < 1e-6 and
        len(row.get('ego_body_vertices_xyz_m', [])) == 8 and
        len(row.get('ego_position_xyz_m', [])) == 3 and
        isinstance(row.get('ego_speed_mps'), (int, float))
        for index, row in enumerate(rows))
    contact_frames = []
    if complete_source:
        for row in rows:
            footprint = MultiPoint([(v[0], v[1]) for v in
                                    row['ego_body_vertices_xyz_m']]).convex_hull
            if footprint.intersects(polygon):
                contact_frames.append(row['frame'])
        first, last = rows[0], rows[-1]
        travel_x = last['ego_position_xyz_m'][0] - first['ego_position_xyz_m'][0]
        endpoint_reached = travel_x >= 9.5 and last['ego_position_xyz_m'][0] >= 4.5
        stopped = abs(last['ego_speed_mps']) <= 0.3
        contact_matched = bool(contact_frames) is requested_contact
        status = 'met' if endpoint_reached and stopped and contact_matched else 'not_met'
    else:
        travel_x, endpoint_reached, stopped, contact_matched = None, False, False, False
        status = 'unverified'
    method = ('600 consecutive 20 Hz actor/body samples; footprint-polygon '
              'intersection, route endpoint, and terminal speed')
    return {
        'physical_checks': {'maneuver': {'status': status, 'method': method,
                                         'sources': sources}},
        'maneuver_completed': status == 'met',
        'realized_observables': ({'sampled_travel_x_m': travel_x,
                                 'surveyed_contact_frame_count': len(contact_frames),
                                 'requested_contact_matched': contact_matched,
                                 'endpoint_reached': endpoint_reached,
                                 'terminal_stopped': stopped}
                                if complete_source else {}),
        'provenance_kind': provenance_kind,
        'diagnostic_fixture': diagnostic_fixture,
        'physical_or_legal_acceptance_claimed': False,
    }
