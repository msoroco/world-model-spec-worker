"""Native waypoint geometry screen for prospective NRS 484B.407 U-turn sites.

This records curve/crest candidates on both incoming approaches. Actual 500 ft
body-ray visibility, physical obstruction and applicability require Native
capture and independent review; waypoint geometry alone proves none of them.
"""
from math import acos, hypot, isfinite, pi

PROBE_M = 152.4  # 500 statutory feet
ROUTE_M = 230.0  # engineering route extent beyond the visibility probe
STEP_M = 10.0


def _point(waypoint):
    loc = waypoint.transform.location
    point = [float(loc.x), float(loc.y), float(loc.z)]
    if not all(isfinite(value) for value in point):
        raise ValueError('Nonfinite Native road point')
    return point


def _lane_samples(lane, *, extent_m=ROUTE_M, step_m=STEP_M):
    if not isfinite(extent_m) or extent_m < PROBE_M or not isfinite(step_m) or step_m <= 0:
        raise ValueError('Invalid sight-route sampling request')
    rows = [{'distance_m': 0.0, 'xyz_m': _point(lane)}]
    current = lane
    distance = 0.0
    while distance + step_m <= extent_m + 1e-8:
        prior = current.previous(step_m)
        if len(prior) != 1 or prior[0] is None or 'Driving' not in str(prior[0].lane_type):
            raise ValueError('Incoming Native road route missing or ambiguous')
        current = prior[0]
        distance += step_m
        rows.append({'distance_m': round(distance, 6), 'xyz_m': _point(current)})
    if rows[-1]['distance_m'] < PROBE_M:
        raise ValueError('Incoming Native route shorter than statutory probe')
    return rows


def _deflection_deg(rows):
    vectors = []
    for a, b in zip(rows, rows[1:]):
        dx = b['xyz_m'][0] - a['xyz_m'][0]
        dy = b['xyz_m'][1] - a['xyz_m'][1]
        length = hypot(dx, dy)
        if length <= 1e-6:
            raise ValueError('Degenerate Native sight-route segment')
        vectors.append((dx / length, dy / length))
    return sum(acos(max(-1.0, min(1.0, a[0]*b[0]+a[1]*b[1]))) * 180.0/pi
               for a,b in zip(vectors, vectors[1:]))


def _probe_point(rows, distance_m=PROBE_M):
    for a, b in zip(rows, rows[1:]):
        if a['distance_m'] <= distance_m <= b['distance_m']:
            fraction = (distance_m-a['distance_m'])/(b['distance_m']-a['distance_m'])
            return [x + fraction*(y-x) for x,y in zip(a['xyz_m'], b['xyz_m'])]
    raise ValueError('Statutory probe lies beyond Native route')


def _crest_prominence_m(rows, probe_xyz):
    """Elevation above the straight endpoint chord within the first 500 ft."""
    end_d = PROBE_M
    if end_d <= 0:
        raise ValueError('No Native crest probe')
    start_z = rows[0]['xyz_m'][2]
    end_z = probe_xyz[2]
    return max(row['xyz_m'][2] - (start_z + (end_z-start_z)*row['distance_m']/end_d)
               for row in rows if row['distance_m'] <= end_d)


def inspect_407_geometry(scene, *, extent_m=ROUTE_M, step_m=STEP_M):
    """Retain both original lane geometries and engineering candidate metrics."""
    result = {}
    for name in ('approach', 'opposite'):
        lane = scene[name]
        rows = _lane_samples(lane, extent_m=extent_m, step_m=step_m)
        probe_xyz = _probe_point(rows)
        result[name] = {'road_id': int(lane.road_id), 'lane_id': int(lane.lane_id),
                        'samples': rows, 'probe_xyz_m': probe_xyz,
                        'cumulative_deflection_deg': _deflection_deg(rows),
                        'crest_prominence_m': _crest_prominence_m(rows, probe_xyz)}
    return {'method': 'Native incoming-lane waypoint elevation and heading screen',
            'statutory_sight_probe_m': PROBE_M,
            'curve_or_crest_legal_finding': None,
            'both_direction_body_ray_visibility': None,
            'physical_occlusion_verified': False,
            'directions': result}


def candidate_screen(report, *, deflection_deg=8.0, crest_prominence_m=0.5):
    """Engineering search only; thresholds are not legal boundaries."""
    if not isfinite(deflection_deg) or deflection_deg <= 0 or not isfinite(crest_prominence_m) or crest_prominence_m <= 0:
        raise ValueError('Invalid engineering geometry screen')
    return any(side['cumulative_deflection_deg'] >= deflection_deg or
               side['crest_prominence_m'] >= crest_prominence_m
               for side in report['directions'].values())


def validate_geometry_packet(packet, context):
    """Recompute the saved map packet without claiming a visible obstruction."""
    if (not isinstance(packet, dict) or
            packet.get('method') != 'Native incoming-lane waypoint elevation and heading screen' or
            packet.get('statutory_sight_probe_m') != PROBE_M or
            packet.get('curve_or_crest_legal_finding') is not None or
            packet.get('both_direction_body_ray_visibility') is not None or
            packet.get('physical_occlusion_verified') is not False):
        raise ValueError('Original 407 geometry identity or legal status differs')
    directions = packet.get('directions')
    if not isinstance(directions, dict) or set(directions) != {'approach','opposite'}:
        raise ValueError('Original 407 two-direction geometry missing')
    for name, lane_key in (('approach','approach_lane_id'),
                           ('opposite','opposite_lane_id')):
        side = directions[name]
        rows = side.get('samples')
        if (side.get('road_id') != context.get('approach_road_id') or
                side.get('lane_id') != context.get(lane_key) or
                not isinstance(rows, list) or len(rows)<2 or
                rows[0].get('distance_m') != 0 or
                rows[-1].get('distance_m',0) < ROUTE_M or
                any(not all(isfinite(float(v)) for v in row.get('xyz_m',[])) or
                    len(row.get('xyz_m',[])) != 3 for row in rows) or
                any(b['distance_m'] <= a['distance_m']
                    for a,b in zip(rows,rows[1:]))):
            raise ValueError('Original 407 sampled route differs')
        probe = _probe_point(rows)
        if (any(abs(a-b)>1e-6 for a,b in zip(probe,side.get('probe_xyz_m',[]))) or
                abs(_deflection_deg(rows)-side.get('cumulative_deflection_deg',-1))>1e-6 or
                abs(_crest_prominence_m(rows,probe)-side.get('crest_prominence_m',-1))>1e-6):
            raise ValueError('Original 407 curve or crest metric differs')
    if not candidate_screen(packet):
        raise ValueError('Original 407 curve/crest candidate absent')
    return packet


def select_407_candidate(carla_map, *, waypoint_spacing_m=2.0, max_candidates=500):
    """Search Native opposing-lane sites for a measurable curve or crest.

    Selection is an engineering request only. It cannot establish a 407
    prohibition without saved body-ray obstruction and physical/legal review.
    """
    from u_turn_construction import select_u_turn_scene
    if type(max_candidates) is not int or max_candidates <= 0:
        raise ValueError('Invalid 407 candidate search limit')
    for index in range(max_candidates):
        try:
            scene = select_u_turn_scene(carla_map,
                                        waypoint_spacing_m=waypoint_spacing_m,
                                        candidate_index=index)
        except ValueError as error:
            if 'No requested Native opposing-lane U-turn pair' in str(error):
                break
            raise
        try:
            report = inspect_407_geometry(scene)
        except ValueError:
            continue
        if candidate_screen(report):
            report['candidate_index'] = index
            return scene, report
    raise ValueError('No Native 407 curve/crest candidate with both incoming routes')
