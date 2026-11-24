"""Opt-in measurements that supplement the native scene graph.

Call actor_visibility once per observed/replayed frame. It reads the actual actor
pose and map, not controller targets or fixed turn-site calibration points. These
measurements do not independently validate extraction accuracy or judge compliance.

Distances along incoming lanes are waypoint-route distances in metres. Rays from
observer eyes to body samples are straight 3-D segments. Route distance is not the
Euclidean length of a ray or distance to a fixed blocker.

Original-run speed must come from separately sourced telemetry: recorder replay
velocity is not a reliable substitute. NONE-labelled ray collisions are retained
because custom OpenDRIVE walls use that label.
"""
import math


def xyz(point):
    return [point.x, point.y, point.z]


def ray_evidence(world, actor, observer, target):
    """Return collision evidence for one straight observer-to-target ray.

    Exclude hits inside the subject's current bounding box and endpoint margins
    (0.05 m at the eye, 0.02 m at the target). Retain all other labels, including
    NONE, so unlabeled custom geometry is not treated as transparent. Blocker
    distances are Euclidean distances from the observer, in metres. ``clear``
    means no retained CARLA collision, not human recognizability; collision meshes
    and these filtering rules limit what this measurement proves.
    """
    transform = actor.get_transform()
    hits = []
    for hit in world.cast_ray(observer, target):
        if actor.bounding_box.contains(hit.location, transform):
            continue
        if hit.location.distance(observer) < .05 or hit.location.distance(target) < .02:
            continue
        hits.append({'label': str(hit.label), 'location_m': xyz(hit.location),
                     'distance_from_observer_m': hit.location.distance(observer)})
    hits.sort(key=lambda h: h['distance_from_observer_m'])
    return {'observer_m': xyz(observer), 'target_m': xyz(target),
            'clear': not hits, 'blockers': hits}


def sampled_horizon(sample, maximum, step, tolerance, checkpoints=()):
    """Scan any-clear rays; retain a clear/blocked bracket and censoring evidence.

    sample(distance) returns ray records or None for a missing/ambiguous route.
    Narrow or nonmonotone occlusions between coarse samples remain a limitation.
    """
    if not all(math.isfinite(v) and v > 0 for v in (maximum, step, tolerance)):
        raise ValueError('Horizon search parameters must be finite and positive')
    initial = sample(0.)
    if initial is None:
        return {'distance_m': 0., 'bound': 'route_limit', 'unknown': True}
    if not any(r['clear'] for r in initial):
        return {'distance_m': 0., 'bracket_m': [0., 0.],
                'bound': 'first_sampled_occlusion', 'blocked_rays': initial}
    last = 0.
    distances = sorted(set([min(i*step, maximum) for i in range(1, math.ceil(maximum/step)+1)] +
                           [d for d in checkpoints if 0 < d <= maximum]))
    for d in distances:
        rays = sample(d)
        if rays is None:
            return {'distance_m': last, 'bound': 'route_limit', 'unknown': True}
        if not any(r['clear'] for r in rays):
            low, high = last, d
            while high-low > tolerance:
                mid = (low+high)/2
                middle = sample(mid)
                if middle is None:
                    return {'distance_m': low, 'bound': 'route_limit', 'unknown': True}
                if any(r['clear'] for r in middle): low = mid
                else: high = mid
            return {'distance_m': (low+high)/2, 'bracket_m': [low, high],
                    'bound': 'first_sampled_occlusion', 'blocked_rays': rays,
                    'blocker': rays[0]['blockers'][0] if rays[0]['blockers'] else None}
        last = d
        if d == maximum:
            return {'distance_m': maximum, 'bound': 'at_least'}


def actor_visibility(world, actor, distance_m=152.4, max_distance_m=230.,
                     eye_height_m=1.4, search_step_m=10., tolerance_m=.25,
                     mapping=None, lane_inventory=None, route_topology=None):
    """Measure visibility toward the current actor from incoming lane routes.

    Geometry and viewpoints:
        Project the actual actor onto a driving waypoint. At that road station,
        select every inventoried driving lane on that road, then walk upstream
        along the complete modeled route. Unique declared XML road/junction
        relations may recover a missing native lane link only when the driving-lane
        endpoints coincide and their incoming tangents align. At a verified outer
        terminal, continue the virtual route along the native 3-D endpoint tangent.
        Junction ambiguity, missing topology and missing tangents remain unknown. Observers are virtual eyes eye_height_m
        above waypoints, not spawned vehicles or fixed cameras. Recompute both
        viewpoints and body targets every frame, including throughout a U-turn.

    Separate measurements:
        At distance_m (default 152.4 m / 500 ft), cast rays to the body's centre
        and eight bounding-box corners. any_sample_clear_at_probe means at least
        one sample has a clear ray; it is not a legal seeing test.
        Scan both centre rays (diagnostic) and any-of-nine body visibility in
        search_step_m increments, then bisect each first sampled clear-to-blocked
        interval to tolerance_m. The any-body scan is the scalar source. This is a sampled
        horizon, not a proven continuous visibility envelope. Narrow occlusions
        between scan points or nonmonotone visibility can be missed; bisection
        does not remove that coarse-search limitation.

    Interpret either sight horizon's bound before using its distance_m:
        first_sampled_occlusion: refined bracket midpoint; bracket_m records the
            interval. blocked_rays comes from the first blocked coarse sample, not
            necessarily the refined boundary rays.
        at_least: no blocker found at sampled distances through max_distance_m
            (default 230 m). A search-censored lower bound under the sampling
            assumptions, NOT a measured physical cutoff at 230 m.
        route_limit: upstream route missing or ambiguous. distance_m is the last
            clear sampled distance and unknown is True, not a blocker distance.
        Missing lanes/probe routes also carry unknown_reason, not a verdict.

    A nearly constant horizon while the actor moves can be genuine: along a
    uniform circular bend, actor, observers and wall intersections move together
    while their relative geometry remains similar. This is not distance to one
    fixed object. A plateau at max_distance_m instead indicates search censoring.

    Legal recognizability, the manoeuvre interval, and sample adequacy require
    separate review. No legal verdict is issued. mapping/lane_inventory allow
    callers to reuse map data between frames.
    """
    import carla
    transform = actor.get_transform()
    mapping = mapping or world.get_map()
    anchor = mapping.get_waypoint(transform.location, project_to_road=True,
                                  lane_type=carla.LaneType.Driving)
    centre = transform.transform(carla.Location(actor.bounding_box.location))
    points = [centre] + list(actor.bounding_box.get_world_vertices(transform))
    result = {'method': ACTOR_VISIBILITY_METHOD,
              'distance_convention': 'modeled incoming waypoint route then verified terminal 3-D straight tangent, measured from actual actor projected station',
              'observer_route_contract': visibility_route_contract(),
              'actual_actor_origin_m': xyz(transform.location),
              'probe_distance_m': distance_m, 'eye_height_m': eye_height_m,
              'horizon_tolerance_m': tolerance_m, 'scan_step_m': search_step_m,
              'maximum_search_distance_m': max_distance_m,
              'maximum_observer_route_distance_m': max(distance_m, max_distance_m),
              'limitations': ['Nine body samples do not define legal recognizability.',
                             'Sampled horizons may miss occlusions narrower than scan_step_m.',
                             'Any of nine samples is the declared seeing criterion; manoeuvre interval requires review.'],
              'ego_body_samples_m': [xyz(p) for p in points], 'approaches': []}
    if anchor is None:
        result['unknown_reason'] = 'no projected driving waypoint'; return result
    result['ego_projection'] = {'road_id': anchor.road_id, 's_m': anchor.s,
                                'lane_id': anchor.lane_id}
    inventory = lane_inventory if lane_inventory is not None else discover_driving_lanes(mapping)
    candidates = inventory.get(anchor.road_id, [])
    result['visibility_criterion'] = 'any_of_nine_body_samples'
    result['required_lane_ids'] = sorted(candidates)
    if not candidates:
        result['unknown_reason'] = 'no driving lanes inventoried'; return result
    for lane_id in sorted(candidates):
        sign = 1 if lane_id > 0 else -1
        lane = mapping.get_waypoint_xodr(anchor.road_id, lane_id, anchor.s)
        if lane is None:
            result['approaches'].append({'direction_sign': sign, 'lane_id': lane_id,
                                        'unknown_reason': 'lane unavailable at ego station'}); continue
        # Move the virtual eye with the current ego-projected station;
        # do not leave it at the planned turn site.
        route = IncomingObserverRoute(mapping, lane, max(distance_m, max_distance_m), topology=route_topology)
        def observer(distance):
            position = route.position(distance)
            if position is None:
                return None
            return carla.Location(x=position[0], y=position[1], z=position[2]+eye_height_m)
        entry = {'direction_sign': sign, 'lane_id': lane.lane_id}
        eye = observer(distance_m)
        if eye is None:
            entry['probe_unknown_reason'] = 'probe route missing or ambiguous'
        else:
            entry['body_rays_at_probe'] = [ray_evidence(world, actor, eye, p) for p in points]
            entry['any_sample_clear_at_probe'] = any(r['clear'] for r in entry['body_rays_at_probe'])
        def sample(distance, targets):
            eye = observer(distance)
            if eye is None:
                return None
            return [ray_evidence(world, actor, eye, p) for p in targets]
        entry['centre_sight_horizon'] = sampled_horizon(
            lambda d: sample(d, [centre]), max_distance_m, search_step_m, tolerance_m, checkpoints=[distance_m])
        entry['any_body_sight_horizon'] = sampled_horizon(
            lambda d: sample(d, points), max_distance_m, search_step_m, tolerance_m, checkpoints=[distance_m])
        entry['observer_route'] = route.provenance()
        result['approaches'].append(entry)
    return result


def with_observed_evidence(graph, evidence):
    """Return a copy with explicit observation provenance, preserving native attrs.

    Supports base and abstract graphs. Store a deep copy at graph level and on
    the ego node when present, preserving native attributes. Attaching evidence
    does not recompute or independently validate it. Replay kinematics are not
    promoted to original-run speed; use observed speed and its source provenance.
    """
    import copy
    enriched = copy.deepcopy(graph)
    enriched.graph['observed_evidence'] = copy.deepcopy(evidence)
    for node in enriched:
        if str(node) == 'ego':
            attrs = getattr(node, 'attr', None)
            if attrs is None:
                attrs = enriched.nodes[node]
            attrs['observed_evidence'] = copy.deepcopy(evidence)
            attrs['native_kinematics_provenance'] = 'recorder_replay; not original velocity telemetry'
    return enriched


def discover_driving_lanes(mapping):
    """Direct sampling supplements topology, which can omit valid custom-map lanes."""
    import carla
    inventory = {}
    points = [p for pair in mapping.get_topology() for p in pair]
    if hasattr(mapping, 'generate_waypoints'):
        points += mapping.generate_waypoints(1.)
    for p in points:
        if p.lane_type == carla.LaneType.Driving:
            inventory.setdefault(p.road_id, set()).add(p.lane_id)
    return {road: sorted(lanes) for road, lanes in inventory.items()}


def complete_missing_lane_segments(mapping, segments, spacing):
    """Recover entirely missing lane sections; do not invent junction connectivity.

    Sample only actual CARLA driving waypoints. Missing sections become sequential
    lane chains in travel direction. Inter-section/junction links are not inferred.
    """
    import carla
    covered = {(p.road_id, p.section_id, p.lane_id)
               for seg in segments for p in [seg['entry'], seg['exit']] + list(seg['path'])}
    groups = {}
    for p in mapping.generate_waypoints(spacing):
        key = (p.road_id, p.section_id, p.lane_id)
        if p.lane_type == carla.LaneType.Driving and key not in covered:
            groups.setdefault(key, []).append(p)
    additions = []
    for key, points in sorted(groups.items()):
        points.sort(key=lambda p:p.s)
        if len(points)<2:continue
        delta=points[1].transform.location-points[0].transform.location
        forward=points[0].transform.get_forward_vector()
        if delta.x*forward.x+delta.y*forward.y+delta.z*forward.z<0:points.reverse()
        additions.append({'entry':points[0],'exit':points[-1],'path':points[1:-1]})
    return list(segments)+additions


# This source is embedded in law_evidence.py by the external preparation tool.
ACTOR_VISIBILITY_METHOD = 'actual_actor_body_raycast_v3'
_OBSERVER_ROUTE_MODELS = []


def modeled_observer_routes(mapping):
    """Read unchanged OpenDRIVE once per map; never amend the scene or map."""
    for previous, value in _OBSERVER_ROUTE_MODELS:
        if previous is mapping:
            return value
    import hashlib
    import xml.etree.ElementTree as ET
    try:
        text = mapping.to_opendrive()
        root = ET.fromstring(text)
        roads = {}
        for road in root.findall('road'):
            sections = []
            for section in road.findall('lanes/laneSection'):
                lanes = {}
                for lane in section.findall('left/lane') + section.findall('right/lane'):
                    lanes[int(lane.get('id'))] = {
                        'type': lane.get('type'),
                        'links': {side: int(link.get('id')) for side, tag in
                                  [('start', 'predecessor'), ('end', 'successor')]
                                  for link in lane.findall('link/' + tag)}}
                sections.append({'s': float(section.get('s')), 'lanes': lanes})
            roads[int(road.get('id'))] = {
                'length': float(road.get('length')), 'junction': road.get('junction', '-1'),
                'sections': sections,
                'links': {side: dict(link.attrib) for side, tag in
                          [('start', 'predecessor'), ('end', 'successor')]
                          for link in road.findall('link/' + tag)}}
        junctions = {j.get('id'): [dict(c.attrib, lane_links=[dict(x.attrib)
                     for x in c.findall('laneLink')]) for c in j.findall('connection')]
                     for j in root.findall('junction')}
        reverse_links = {}
        for ident, road in roads.items():
            for side, link in road['links'].items():
                if link.get('elementType') == 'road' and link.get('contactPoint') in ('start', 'end'):
                    reverse_links.setdefault((int(link['elementId']), link['contactPoint']), []).append((ident, side, None))
        value = {'roads': roads, 'junctions': junctions, 'reverse_road_links': reverse_links,
                 'map_sha256': hashlib.sha256(text.encode()).hexdigest()}
    except (AttributeError, TypeError, ValueError, ET.ParseError):
        value = None
    _OBSERVER_ROUTE_MODELS.append((mapping, value))
    del _OBSERVER_ROUTE_MODELS[:-4]
    return value


def visibility_route_contract():
    return {
        'measurement_method': ACTOR_VISIBILITY_METHOD,
        'observer_route_method': 'native_modeled_route_then_straight_terminal_tangent_v1',
        'endpoint_access': 'exact native endpoint, else one-sided native pose/tangent within 1e-3 native station metres; actual gap and sampled tangent error recorded per endpoint',
        'terminal_tangent_axis': 'unit 3-D opposite native forward; no terrain or physical road extrapolation',
        'distance_origin': 'actual actor projected road station, shared across current-road lanes',
        'distance_metric': 'native waypoint-route metres inside the model, then 3-D straight tangent metres',
        'terminal_rule': 'outer road endpoint with no declared exit link; not a junction or unresolved connection',
        'connection_rule': 'native unique predecessor, or declared XML road/junction relation with one coincident aligned driving-lane endpoint',
        'endpoint_position_tolerance_m': .001,
        'endpoint_tangent_dot_tolerance': .000001,
        'eye_height_axis': 'world vertical above virtual route position',
        'occluder_scope': 'all existing current-world collision geometry through world.cast_ray',
        'out_of_domain_scene_geometry': 'none generated or added',
        'search_bounds': 'first_sampled_occlusion / at_least / route_limit unchanged'}


class NativeEndpointLimit:
    """Numerical one-sided endpoint pose, not new map or world geometry."""
    def __init__(self, mapping, source, boundary, direction, length):
        self.mapping, self.source = mapping, source
        self.road_id, self.lane_id, self.section_id = source.road_id, source.lane_id, source.section_id
        self.is_junction, self.transform, self.s = source.is_junction, source.transform, boundary
        self._upstream_s_direction, self.length = direction, length

    def _move(self, distance, previous):
        direction = self._upstream_s_direction * (1 if previous else -1)
        station = self.s + direction*distance
        if 0 <= station <= self.length:
            point = self.mapping.get_waypoint_xodr(self.road_id, self.lane_id, station)
            return [point] if point is not None else []
        adjusted = distance + (self.s-self.source.s)/direction
        if adjusted <= 0:
            return []
        return (self.source.previous if previous else self.source.next)(adjusted)

    def previous(self, distance):
        return self._move(distance, True)

    def next(self, distance):
        return self._move(distance, False)


class IncomingObserverRoute:
    """Virtual observer positions; source-backed connections, never new roads."""
    def __init__(self, mapping, lane, maximum, topology=None):
        self.mapping, self.lane, self.maximum = mapping, lane, maximum
        self.topology = topology if topology is not None else modeled_observer_routes(mapping)
        self.segments, self.connections, self.positions = [], [], {}
        self.endpoint_proofs = []
        self.endpoint_rejections = []
        self.terminal = None
        self.unknown_reason = None
        self.used_extension = False
        if self.topology is not None:
            self._walk()

    @staticmethod
    def _key(point):
        return point.road_id, point.lane_id, getattr(point, 'section_id', 0), point.s

    @staticmethod
    def _upstream(point):
        f = point.transform.get_forward_vector()
        norm = math.sqrt(f.x*f.x + f.y*f.y + f.z*f.z)
        if not math.isfinite(norm) or norm <= 1e-12 or math.hypot(f.x, f.y) <= 1e-12:
            return None
        return [-f.x/norm, -f.y/norm, -f.z/norm]

    @staticmethod
    def _direction(point, length):
        if hasattr(point, '_upstream_s_direction'):
            return point._upstream_s_direction
        probe = min(.01, length/4)
        if probe <= 0:
            return None
        for method, sign in [(point.previous, 1), (point.next, -1)]:
            choices = method(probe)
            if len(choices) == 1 and choices[0].road_id == point.road_id:
                delta = choices[0].s - point.s
                if abs(delta) > 1e-9:
                    return sign * (1 if delta > 0 else -1)
        return None

    def _related(self, point, side, road):
        link = road['links'].get(side)
        related = list(self.topology.get('reverse_road_links', {}).get((point.road_id, side), []))
        if not link:
            return related
        if link.get('elementType') == 'road':
            section = road['sections'][getattr(point, 'section_id', 0)]
            lane_link = section['lanes'].get(point.lane_id, {}).get('links', {}).get(side)
            related.append((int(link['elementId']), link.get('contactPoint'), lane_link))
        elif link.get('elementType') == 'junction':
            connections = self.topology['junctions'].get(link['elementId'], [])
            for c in connections:
                if int(c['incomingRoad']) == point.road_id:
                    for lane in c['lane_links']:
                        if int(lane['from']) == point.lane_id:
                            related.append((int(c['connectingRoad']), c.get('contactPoint'), int(lane['to'])))
            # Backward travel through the outgoing end of a declared connector.
            for ident in {int(c['connectingRoad']) for c in connections}:
                connector = self.topology['roads'].get(ident, {})
                for end, outgoing in connector.get('links', {}).items():
                    if (outgoing.get('elementType') == 'road'
                            and int(outgoing['elementId']) == point.road_id
                            and outgoing.get('contactPoint') == side):
                        related.append((ident, end, None))
        return list(set(related))

    def _endpoint(self, ident, lane_id, boundary, record=True):
        exact = self.mapping.get_waypoint_xodr(ident, lane_id, boundary)
        if exact is not None:
            return exact
        road = self.topology['roads'][ident]
        if boundary not in (0., road['length']) or not road['sections']:
            return None
        section_span = (road['sections'][1]['s'] if len(road['sections']) > 1 else road['length']) if boundary == 0 else road['length']-road['sections'][-1]['s']
        if section_span <= 0:
            return None
        source = None
        for requested in (.000001, .00001, .0001, .001):
            margin = min(requested, section_span/4)
            station = margin if boundary == 0 else boundary-margin
            candidate = self.mapping.get_waypoint_xodr(ident, lane_id, station)
            if candidate is not None and abs(candidate.s-boundary) <= .0010000001:
                source = candidate
                break
        if source is None:
            return None
        direction = self._direction(source, road['length'])
        vector = self._upstream(source)
        gap = abs(source.s-boundary)
        second_station = 2*gap if boundary == 0 else boundary-2*gap
        second = self.mapping.get_waypoint_xodr(ident, lane_id, second_station)
        other = self._upstream(second) if second is not None else None
        if direction is None or vector is None or other is None:
            return None
        pose_estimate = math.dist(xyz(source.transform.location), xyz(second.transform.location))
        tangent_change = math.dist(vector, other)
        observer_error_estimate = pose_estimate + self.maximum*tangent_change
        if observer_error_estimate > .001:
            self.endpoint_rejections.append({'road_id': ident, 'lane_id': lane_id,
                'boundary_s_m': boundary, 'station_gap_m': gap,
                'sampled_observer_geometry_error_estimate_m': observer_error_estimate,
                'reason': 'one-sided endpoint sampling exceeds 1mm numerical route tolerance'})
            return None
        point = NativeEndpointLimit(self.mapping, source, boundary, direction, road['length'])
        if record:
            proof = {'road_id': ident, 'lane_id': lane_id, 'boundary_s_m': boundary,
                     'native_pose_s_m': source.s, 'station_residue_m': abs(source.s-boundary),
                     'native_pose_m': xyz(source.transform.location),
                     'native_upstream_unit_tangent_3d': self._upstream(source),
                     'sampled_pose_gap_m': pose_estimate,
                     'sampled_unit_tangent_change': tangent_change,
                     'observer_shift_over_search_from_sampled_tangent_change_m': self.maximum*tangent_change,
                     'sampled_observer_geometry_error_estimate_m': observer_error_estimate,
                     'method': 'one-sided native endpoint limit; native float32 pose/tangent, <=1mm station gap, sampled local observer-error estimate <=1mm; not an exact endpoint pose'}
            if proof not in self.endpoint_proofs:
                self.endpoint_proofs.append(proof)
        return point

    def _unlinked_continuation(self, endpoint):
        if '_endpoint_candidates' not in self.topology:
            entries = []
            for ident, road in self.topology['roads'].items():
                if not road['sections']:
                    continue
                for side, station, section in [('start', 0., road['sections'][0]), ('end', road['length'], road['sections'][-1])]:
                    for lane_id, lane in section['lanes'].items():
                        if lane['type'] != 'driving':
                            continue
                        point = self._endpoint(ident, lane_id, station, record=False)
                        if point is None or self._direction(point, road['length']) != (1 if side == 'start' else -1):
                            continue
                        vector = self._upstream(point)
                        if vector is not None:
                            entries.append((self._key(point), xyz(point.transform.location), vector))
            self.topology['_endpoint_candidates'] = entries
        origin, vector = xyz(endpoint.transform.location), self._upstream(endpoint)
        return vector is not None and any(key != self._key(endpoint) and math.dist(origin, position) <= .001
            and sum(a*b for a,b in zip(vector, other)) >= 1.-.000001
            for key,position,other in self.topology['_endpoint_candidates'])

    def _xml_predecessor(self, point, side, road):
        origin, upstream = xyz(point.transform.location), self._upstream(point)
        if upstream is None:
            return []
        candidates = {}
        for ident, end, selected_lane in self._related(point, side, road):
            target = self.topology['roads'].get(ident)
            if target is None or end not in ('start', 'end') or not target['sections']:
                continue
            section = target['sections'][0 if end == 'start' else -1]
            station = 0. if end == 'start' else target['length']
            for lane_id, definition in section['lanes'].items():
                if definition['type'] != 'driving' or selected_lane is not None and lane_id != selected_lane:
                    continue
                other = self._endpoint(ident, lane_id, station)
                if other is None:
                    continue
                direction, vector = self._direction(other, target['length']), self._upstream(other)
                if direction != (1 if end == 'start' else -1) or vector is None:
                    continue
                position = xyz(other.transform.location)
                if (math.dist(origin, position) <= .001
                        and sum(a*b for a, b in zip(upstream, vector)) >= 1.-.000001):
                    candidates[self._key(other)] = other
        return list(candidates.values())

    def _walk(self):
        current, distance = self.lane, 0.
        for _ in range(256):
            road = self.topology['roads'].get(current.road_id)
            section_index = getattr(current, 'section_id', 0)
            if road is None or not 0 <= section_index < len(road['sections']):
                self.unknown_reason = 'modeled road or lane section unavailable'; return
            section = road['sections'][section_index]
            if section['lanes'].get(current.lane_id, {}).get('type') != 'driving':
                self.unknown_reason = 'modeled driving lane unavailable'; return
            direction = self._direction(current, road['length'])
            if direction is None:
                self.unknown_reason = 'native route station direction unavailable'; return
            boundary = (section['s'] if direction < 0 else
                        road['sections'][section_index+1]['s'] if section_index+1 < len(road['sections'])
                        else road['length'])
            span = abs(boundary-current.s)
            if distance+span > self.maximum:
                self.segments.append((distance, self.maximum, current, None)); return
            endpoint = self._endpoint(current.road_id, current.lane_id, boundary)
            if endpoint is None:
                self.unknown_reason = 'native modeled endpoint pose unavailable'; return
            if span > 1e-9:
                self.segments.append((distance, distance+span, current, endpoint))
                distance += span
            if distance >= self.maximum:
                return
            choices = endpoint.previous(.001)
            if len(choices) > 1:
                self.unknown_reason = 'ambiguous modeled predecessor'; return
            if len(choices) == 1 and self._key(choices[0]) != self._key(endpoint):
                self.segments.append((distance, distance+.001, endpoint, choices[0]))
                self.connections.append({'at_distance_m': distance, 'source': 'native unique predecessor'})
                current, distance = choices[0], distance+.001
                if distance >= self.maximum:
                    return
                continue
            side = 'start' if direction < 0 else 'end'
            outer = abs(boundary-(0. if side == 'start' else road['length'])) <= 1e-8
            if outer:
                connected = self._xml_predecessor(endpoint, side, road)
                if len(connected) == 1:
                    other = connected[0]
                    self.connections.append({'at_distance_m': distance,
                        'source': 'declared XML relation; unique coincident aligned driving-lane endpoint',
                        'from_road': current.road_id, 'to_road': other.road_id})
                    current = other
                    continue
                if len(connected) > 1:
                    self.unknown_reason = 'ambiguous declared modeled predecessor'; return
                if (not road['links'].get(side) and not self._related(endpoint, side, road) and road['junction'] == '-1'
                        and not getattr(endpoint, 'is_junction', False)):
                    if self._unlinked_continuation(endpoint):
                        self.unknown_reason = 'unlinked coincident modeled continuation'; return
                    tangent = self._upstream(endpoint)
                    if tangent is None:
                        self.unknown_reason = 'terminal native tangent unavailable'; return
                    self.terminal = {'in_domain_distance_m': distance,
                        'road_id': endpoint.road_id, 'lane_id': endpoint.lane_id,
                        's_m': endpoint.s, 'position_m': xyz(endpoint.transform.location),
                        'upstream_unit_tangent_3d': tangent}
                    return
            self.unknown_reason = 'modeled connection or lane topology unavailable'; return
        self.unknown_reason = 'modeled route boundary traversal limit'

    def position(self, distance):
        if distance in self.positions:
            return self.positions[distance]
        if distance < 0 or distance > self.maximum:
            return None
        if distance == 0:
            value = xyz(self.lane.transform.location)
        elif self.topology is None:
            choices = self.lane.previous(distance)
            value = xyz(choices[0].transform.location) if len(choices) == 1 else None
        elif self.terminal is not None and distance >= self.terminal['in_domain_distance_m']:
            extension = distance-self.terminal['in_domain_distance_m']
            value = [p+extension*t for p,t in zip(self.terminal['position_m'],self.terminal['upstream_unit_tangent_3d'])]
            self.used_extension |= extension > 0
        else:
            value = None
            for start, end, waypoint, endpoint in self.segments:
                if start <= distance <= end:
                    if endpoint is not None and abs(distance-end) <= 1e-8:
                        value = xyz(endpoint.transform.location)
                    else:
                        choices = [waypoint] if distance == start else waypoint.previous(distance-start)
                        if (len(choices) > 1 and endpoint is not None
                                and end-start <= .001+1e-9
                                and waypoint.road_id != endpoint.road_id):
                            # The short bridge already selected this native branch.
                            key = (endpoint.road_id, endpoint.lane_id, endpoint.section_id)
                            choices = [point for point in choices if
                                (point.road_id, point.lane_id, point.section_id) == key]
                        if len(choices) == 1:
                            value = xyz(choices[0].transform.location)
                    break
        self.positions[distance] = value
        return value

    def provenance(self):
        return {'method': 'native_modeled_route_then_straight_terminal_tangent_v1',
                'map_sha256': self.topology['map_sha256'] if self.topology else None,
                'terminal': self.terminal, 'connections': self.connections,
                'modeled_segment_count': len(self.segments),
                'native_endpoint_pose_limits': self.endpoint_proofs,
                'native_endpoint_rejections': self.endpoint_rejections,
                'maximum_route_distance_m': self.maximum,
                'outside_extension_used': self.used_extension,
                'unknown_reason': self.unknown_reason,
                'topology_available': self.topology is not None}


def visibility_acquisition_contract():
    """One producer declaration reused by original capture and replay extraction."""
    import inspect
    parameters = inspect.signature(actor_visibility).parameters
    return {'measurement_method': ACTOR_VISIBILITY_METHOD,
            'capability_method': 'estimate:vehicle_reference_geometry',
            'visibility_criterion': 'any_of_nine_body_samples',
            'body_samples': 'actual current native bounding-box centre plus eight vertices',
            'reciprocity': 'observer-to-actual-body rays are reciprocal by convention',
            'observer_route': visibility_route_contract(),
            'parameters': {name: parameters[name].default for name in
                ('distance_m', 'max_distance_m', 'eye_height_m', 'search_step_m', 'tolerance_m')}}
