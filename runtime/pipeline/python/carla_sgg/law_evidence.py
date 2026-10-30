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
                     mapping=None, lane_inventory=None):
    """Measure visibility toward the current actor from incoming lane routes.

    Geometry and viewpoints:
        Project the actual actor onto a driving waypoint. At that road station,
        select every inventoried driving lane on that road, then walk upstream
        with lane.previous(distance). Junction branches are not silently selected;
        missing or ambiguous routes remain unknown. Observers are virtual eyes eye_height_m
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
    result = {'method': 'actual_actor_body_raycast_v2',
              'distance_convention': 'incoming driving-lane waypoint arc length to actor projected station',
              'probe_distance_m': distance_m, 'eye_height_m': eye_height_m,
              'horizon_tolerance_m': tolerance_m, 'scan_step_m': search_step_m,
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
        def observer(distance):
            # CARLA requires a strictly positive previous() distance.
            choices = [lane] if distance == 0 else lane.previous(distance)
            if len(choices) != 1:
                return None
            return choices[0].transform.location + carla.Location(z=eye_height_m)
        entry = {'direction_sign': sign, 'lane_id': lane.lane_id}
        eye = observer(distance_m)
        if eye is None:
            entry['unknown_reason'] = 'probe route missing or ambiguous'
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
