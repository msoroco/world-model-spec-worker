"""Subject-relative regional sight distance from declared any-body measurements.

The scalar is a conservative sampled minimum across all inventoried approaches,
not a physical cutoff when the search is censored. Detailed rays remain in the
supplement. Never substitute centre horizons or infer a horizon from one probe.
"""
import math

CONVENTION = 'incoming driving-lane waypoint arc length to actor projected station'


def sight_distance(visibility):
    """Return (metres, reason). Unknown coverage/geometry yields no scalar."""
    if not visibility or visibility.get('visibility_criterion') != 'any_of_nine_body_samples':
        return None, 'any-body horizons not captured'
    geometry_reason = _reference_geometry_reason(visibility)
    if geometry_reason or visibility.get('unknown_reason'):
        return None, geometry_reason or 'unknown visibility geometry or distance convention'
    for key in ('eye_height_m', 'scan_step_m', 'horizon_tolerance_m', 'probe_distance_m'):
        value = visibility.get(key)
        if value is None:
            return None, 'missing declared visibility convention: '+key
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid visibility convention: '+key)
    points = visibility.get('ego_body_samples_m', [])
    if len(points) != 9:
        return None, 'nine measured body targets unavailable'
    if any(not isinstance(p, (list, tuple)) or len(p) != 3 or
           any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Invalid visibility body samples')
    probe = visibility['probe_distance_m']
    required = visibility.get('required_lane_ids', [])
    approaches = visibility.get('approaches', [])
    ids = [a.get('lane_id') for a in approaches]
    if not required or len(ids) != len(set(ids)) or set(ids) != set(required):
        return None, 'incomplete approach coverage'
    bounds = []
    for approach in approaches:
        h = approach.get('any_body_sight_horizon', {})
        if approach.get('unknown_reason') or h.get('unknown'):
            return None, 'missing or ambiguous approach route'
        if h.get('bound') == 'first_sampled_occlusion':
            bracket = h.get('bracket_m', [])
            if len(bracket) != 2:
                return None, 'missing visibility bracket'
            low, high = bracket
            tolerance = visibility.get('horizon_tolerance_m')
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) for v in (low, high)) or not 0 <= low <= high:
                raise ValueError('Invalid visibility bracket')
            if tolerance is None or high-low > tolerance+1e-9:
                return None, 'unrefined visibility bracket'
            value = low  # Conservative lower bound, never the uncertain midpoint.
        elif h.get('bound') == 'at_least':
            value = h.get('distance_m')
            # Do not use an unfinished search to classify the declared probe.
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid visibility search bound')
            if value < probe and not _verified_minimum_dominates(visibility, value):
                return None, 'censored search shorter than declared probe'
        else:
            return None, 'unknown horizon bound'
        if value >= probe and approach.get('any_sample_clear_at_probe') is not True:
            return None, 'declared probe absent or inconsistent with horizon'
        route_reason = _reference_route_reason(visibility, approach)
        if route_reason:
            return None, route_reason
        bounds.append(value)
    return min(bounds), 'minimum sampled clear-side bound across all approaches'


def attach_visibility(regions, polygons, footprint, visibility, native_lanes=None):
    """Attach the current subject's operational proxy to occupied lane/roadway regions."""
    from shapely.geometry import MultiPoint
    # Always clear old values; each frame must earn its own source-bound estimate.
    result = [{k:v for k,v in region.items() if k != 'sight_distance'} for region in regions]
    value, reason = sight_distance(visibility)
    mapping = {'value_m': None, 'attached_regions': [], 'reason': reason,
               'method': 'incoming_virtual_observer_to_subject_body',
               'value_kind': 'conservative_sampled_clear_distance'}
    if value is None:
        return result, mapping
    if native_lanes is not None:
        road = visibility.get('ego_projection', {}).get('road_id')
        expected = {lane for source_road, section, lane in native_lanes if source_road == road}
        if not expected or set(visibility['required_lane_ids']) != expected:
            mapping['reason'] = 'approach inventory differs from source driving lanes'
            return result, mapping
    points = visibility['ego_body_samples_m']
    measured_body = MultiPoint([(p[0], -p[1]) for p in points]).convex_hull
    if (footprint is None or footprint.is_empty or measured_body.area <= 0 or
            measured_body.hausdorff_distance(footprint) > 1e-6):
        mapping['reason'] = 'visibility targets differ from current subject footprint'
        return result, mapping
    selected = [r for r in result if r.get('kind') in ('lane', 'roadway', 'one_way_roadway')
                and r['id'] in polygons and polygons[r['id']].intersects(footprint)
                and polygons[r['id']].intersection(footprint).area > 0]
    if not selected:
        mapping['reason'] = 'no measured occupied lane or roadway region'
        return result, mapping
    for region in selected:
        region['sight_distance'] = value
    approaches = visibility['approaches']
    upper = [a['any_body_sight_horizon']['bracket_m'][1] for a in approaches
             if a['any_body_sight_horizon']['bound'] == 'first_sampled_occlusion']
    mapping.update(value_m=value, attached_regions=[r['id'] for r in selected],
                   eye_height_m=visibility['eye_height_m'],
                   visibility_criterion=visibility['visibility_criterion'],
                   distance_convention=visibility['distance_convention'],
                   probe_distance_m=visibility['probe_distance_m'],
                   scan_step_m=visibility['scan_step_m'],
                   horizon_tolerance_m=visibility['horizon_tolerance_m'],
                   lower_bound_m=value, upper_bound_m=min(upper) if upper else None,
                   search_censored=not bool(upper),
                   approaches=approaches,
                   measurement_method=visibility.get('method', 'actual_actor_body_raycast_v2'),
                   maximum_search_distance_m=visibility.get('maximum_search_distance_m'),
                   analytic_source=visibility.get('analytic_source'))
    return result, mapping


# Appended to existing visibility.py; no CARLA dependency in the consumer.
CAPABILITY_METHOD = 'estimate:vehicle_reference_geometry'
TERMINAL_CONVENTION = 'modeled incoming waypoint route then verified terminal 3-D straight tangent, measured from actual actor projected station'
ROUTE_METHOD = 'native_modeled_route_then_straight_terminal_tangent_v1'
ANALYTIC_METHOD = 'source_bound_analytic_body_visibility_v1'
METHOD_DESCRIPTION = ('Estimate from actual subject-body geometry and reciprocal incoming virtual observers; '
    'follow existing native modeled roads and source-unique declared connections, then a verified terminal native 3-D tangent. '
    'Preserve all existing-world collision occluders for acquisition, or qualify complete retained reference geometry for analytical clearance. '
    'Keep observer height, actual origin, route/endpoint sampling, probe/search limits, first-loss brackets and censoring; '
    'one-sided endpoint sampling is an empirical numerical estimate, not a rigorous far-observer error bound.')


class _VerifiedAnalyticVisibility(dict):
    """In-memory result of verified source loading; ordinary JSON cannot attest it."""
    def _digest(self):
        import hashlib,json
        return hashlib.sha256(json.dumps(self,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def seal(self):
        self._source_digest=self._digest()
        return self
    def intact(self):
        return getattr(self,'_source_digest',None)==self._digest()


def _finite_vector(value):
    return (isinstance(value, (list, tuple)) and len(value) == 3 and
            all(type(x) in (int, float) and math.isfinite(x) for x in value))


def _verified_minimum_dominates(visibility, lower):
    """A source-verified finite minimum can make a farther unknown tail irrelevant."""
    aggregate = visibility.get('analytic_source', {}).get('minimum_path_horizon', {})
    return (visibility.get('method') == ANALYTIC_METHOD
            and isinstance(visibility, _VerifiedAnalyticVisibility) and visibility.intact()
            and aggregate.get('bound') == 'first_sampled_occlusion'
            and lower >= aggregate['bracket_m'][1])


def _reference_geometry_reason(visibility):
    convention = visibility.get('distance_convention')
    if convention == CONVENTION:
        # Existing complete native-only v2 measurements retain their own geometry.
        return None if visibility.get('method') in (None, 'actual_actor_body_raycast_v2') else 'unknown native-only visibility method'
    if convention != TERMINAL_CONVENTION or visibility.get('method') not in ('actual_actor_body_raycast_v3', ANALYTIC_METHOD):
        return 'unknown visibility geometry or distance convention'
    if not _finite_vector(visibility.get('actual_actor_origin_m')):
        return 'actual actor origin unavailable'
    for key in ('maximum_search_distance_m', 'maximum_observer_route_distance_m'):
        value = visibility.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            return 'missing declared visibility search limit'
    if visibility.get('method') == ANALYTIC_METHOD:
        proof = visibility.get('analytic_source')
        if (not isinstance(visibility,_VerifiedAnalyticVisibility) or not visibility.intact()
                or not isinstance(proof, dict) or proof.get('schema') != 'verified_source_bound_analytic_reference_v1'
                or proof.get('no_cast_ray_executed') is not True or proof.get('source_inputs_verified') is not True):
            return 'analytical visibility source closure unavailable'
    else:
        contract = visibility.get('observer_route_contract', {})
        if (contract.get('observer_route_method') != ROUTE_METHOD
                or contract.get('occluder_scope') != 'all existing current-world collision geometry through world.cast_ray'
                or contract.get('out_of_domain_scene_geometry') != 'none generated or added'):
            return 'unknown observer route or occluder contract'
    return None


def _reference_route_reason(visibility, approach):
    if visibility['distance_convention'] == CONVENTION:
        return None
    alternatives = approach.get('observer_routes')
    if alternatives is not None:
        if (visibility.get('method') != ANALYTIC_METHOD
                or not isinstance(visibility, _VerifiedAnalyticVisibility)
                or not visibility.intact() or not alternatives):
            return 'unverified analytical route alternatives'
        for alternative in alternatives:
            single = dict(approach)
            single.pop('observer_routes')
            single['observer_route'] = alternative
            reason = _reference_route_reason(visibility, single)
            if reason:
                return reason
        return None
    route = approach.get('observer_route', {})
    digest = route.get('map_sha256')
    if (route.get('method') != ROUTE_METHOD or route.get('topology_available') is not True
            or not isinstance(digest, str) or len(digest) != 64 or any(x not in '0123456789abcdef' for x in digest)):
        return 'observer route source geometry unavailable'
    maximum = visibility['maximum_search_distance_m']
    route_limit = route.get('maximum_route_distance_m')
    if type(route_limit) not in (int, float) or not math.isfinite(route_limit) or route_limit < max(maximum, visibility['probe_distance_m']):
        return 'incomplete observer route search scope'
    horizon = approach['any_body_sight_horizon']
    if horizon['bound'] == 'at_least' and (route.get('unknown_reason') or abs(horizon['distance_m']-maximum) > 1e-6):
        # Only the actual source reader can establish that this lower bound's
        # unresolved tail cannot affect the complete place-level minimum.
        if route.get('unknown_reason') or not _verified_minimum_dominates(visibility, horizon['distance_m']):
            return 'unfinished observer route or censored search'
    terminal = route.get('terminal')
    if route.get('outside_extension_used'):
        if not isinstance(terminal, dict) or not _finite_vector(terminal.get('position_m')) or not _finite_vector(terminal.get('upstream_unit_tangent_3d')):
            return 'terminal observer geometry unavailable'
        direction = terminal['upstream_unit_tangent_3d']
        domain = terminal.get('in_domain_distance_m')
        if (type(domain) not in (int, float) or not math.isfinite(domain) or domain < 0
                or abs(sum(x*x for x in direction)-1.) > 1e-6):
            return 'invalid terminal observer geometry'
        rays = approach.get('body_rays_at_probe')
        if rays is not None and visibility['probe_distance_m'] >= domain:
            expected = [p+(visibility['probe_distance_m']-domain)*t for p,t in zip(terminal['position_m'],direction)]
            expected[2] += visibility['eye_height_m']
            if len(rays) != 9 or any(not _finite_vector(r.get('observer_m')) or math.dist(r['observer_m'],expected) > .001 for r in rays):
                return 'observer probe differs from terminal route geometry'
    return None


def _constant_native_ground_ceiling(xml, sidewalk_height=0.):
    """Bound one-piece constant source elevations, with source-qualified sidewalks."""
    import struct
    elevations=[]
    for tag in ('elevation','superelevation','crossfall'):
        for record in xml.iter(tag):
            values=[float(record.get(k,'0'))for k in ('a','b','c','d')]
            if any(not math.isfinite(v)for v in values):raise ValueError('Nonfinite analytical elevation/banking')
            if any(values[1:])or(tag!='elevation'and values[0]!=0):raise ValueError('Unsupported varying analytical elevation/banking')
            if tag=='elevation':elevations.append(values[0])
    if not any(elevations)and not sidewalk_height:return False,0.
    for road in xml.findall('road'):
        records=road.findall('./elevationProfile/elevation')
        if len(records)>1 or(records and float(records[0].get('s','nan'))!=0):raise ValueError('Ambiguous constant analytical elevation')
    if sidewalk_height:
        elevations=[(float(records[0].get('a','0'))if records else 0.) +
                    (sidewalk_height if any(l.get('type')=='sidewalk'for l in road.findall('./lanes/laneSection/*/lane'))else 0.)
                    for road in xml.findall('road')
                    for records in [road.findall('./elevationProfile/elevation')]]
    try:
        top=struct.unpack('!f',struct.pack('!f',max(elevations)))[0]
        bits=struct.unpack('!I',struct.pack('!f',top))[0]
        ceiling=struct.unpack('!f',struct.pack('!I',1 if top==0 else bits-1 if top<0 else bits+1))[0]
    except(OverflowError,struct.error):raise ValueError('Unrepresentable analytical elevation')
    if not math.isfinite(ceiling):raise ValueError('Unrepresentable analytical elevation')
    return True,ceiling


def _source_reference_ground_plane(xml, declared, wall_height):
    """One standalone straight Native road, with a single unbanked affine surface."""
    import struct
    def number(node, name):
        try:value=float(node.attrib[name])
        except (KeyError,TypeError,ValueError):raise ValueError('Incomplete affine ground source')
        if not math.isfinite(value):raise ValueError('Nonfinite affine ground source')
        return value
    if (not isinstance(declared,dict) or set(declared)!={'schema','coefficients_m'}
            or declared['schema']!='native_affine_ground_plane_v1'
            or not _finite_vector(declared['coefficients_m']) or wall_height!=0):
        raise ValueError('Invalid affine ground declaration or wall height')
    roads=xml.findall('road')
    if len(roads)!=1 or xml.findall('junction'):
        raise ValueError('Affine ground requires one standalone road')
    road=roads[0]
    if (road.get('junction')!='-1' or road.findall('./link/*')
            or road.findall('./objects/*') or road.findall('./signals/*')):
        raise ValueError('Affine ground has connected roads or object/signal declarations')
    length=number(road,'length');plans=road.findall('./planView/geometry')
    elevations=road.findall('./elevationProfile/elevation')
    if length<=0 or len(plans)!=1 or len(elevations)!=1:
        raise ValueError('Incomplete one-piece affine ground geometry')
    plan=plans[0];elevation=elevations[0]
    if (len(list(plan))!=1 or plan.find('line')is None or number(plan,'s')!=0
            or number(plan,'length')!=length or number(elevation,'s')!=0
            or number(elevation,'c')!=0 or number(elevation,'d')!=0):
        raise ValueError('Affine ground requires one LINE and linear elevation')
    for tag in ('superelevation','crossfall'):
        for record in road.iter(tag):
            if any(number(record,k)!=0 for k in ('a','b','c','d')):
                raise ValueError('Affine ground does not support banking')
    lanes=road.findall('./lanes/laneSection/*/lane')
    if (not lanes or not any(l.get('type')=='driving'for l in lanes)
            or any(l.get('type')not in ('driving','none') or l.findall('height')for l in lanes)):
        raise ValueError('Affine ground has unsupported lane surface geometry')
    x=number(plan,'x');native_y=-number(plan,'y');heading=number(plan,'hdg')
    base=number(elevation,'a');slope=number(elevation,'b')
    if heading!=0 or road.findall('./surface/*') or any(n.tag not in ('superelevation','crossfall') for n in road.findall('./lateralProfile/*')):
        raise ValueError('Unsupported affine ground heading/shape/surface')
    offsets=road.findall('./lanes/laneOffset')
    if len(offsets)>1 or any(number(n,'s')!=0 or any(number(n,k)!=0 for k in ('a','b','c','d')) for n in offsets):
        raise ValueError('Unsupported affine lane offset')
    sections=road.findall('./lanes/laneSection')
    if len(sections)!=1 or number(sections[0],'s')!=0:
        raise ValueError('Unsupported affine lane sections')
    centre=sections[0].findall('center/lane')
    if (len(centre)!=1 or centre[0].get('id')!='0' or centre[0].get('type')!='none'
            or centre[0].findall('width') or centre[0].findall('border')):
        raise ValueError('Unsupported affine centre lane')
    lateral_extent=0.
    for side in ('left','right'):
        side_lanes=sections[0].findall(side+'/lane');ids=[];side_width=0.
        for lane in side_lanes:
            try:ident=int(lane.attrib['id'])
            except (KeyError,ValueError):raise ValueError('Invalid affine source lane id')
            if lane.get('type')!='driving' or lane.get('level')!='false':
                raise ValueError('Unsupported affine driving lane geometry')
            widths=lane.findall('width')
            if (len(widths)!=1 or lane.findall('border') or number(widths[0],'sOffset')!=0
                    or number(widths[0],'a')<=0 or any(number(widths[0],k)!=0 for k in ('b','c','d'))):
                raise ValueError('Unsupported affine lane widths')
            ids.append(ident);side_width+=number(widths[0],'a')
        expected_ids=list(range(1,len(ids)+1)) if side=='left' else list(range(-len(ids),0))
        if sorted(ids)!=expected_ids:raise ValueError('Ambiguous affine driving lane coverage')
        lateral_extent=max(lateral_extent,side_width)
    gx=slope;gy=0.
    expected=[gx,gy,base-gx*x-gy*native_y]
    if list(declared['coefficients_m'])!=expected:
        raise ValueError('Declared affine ground differs from retained Native XML')
    try:
        scale=max(1.,abs(x),abs(x+length),abs(native_y)+lateral_extent,abs(base),abs(base+slope*length))
        source_margin=(64*2**-23+64*2**-52)*scale*(1+abs(slope))
        top=struct.unpack('!f',struct.pack('!f',max(base,base+slope*length)+source_margin))[0]
        bits=struct.unpack('!I',struct.pack('!f',top))[0]
        upper=struct.unpack('!f',struct.pack('!I',1 if top==0 else bits-1 if top<0 else bits+1))[0]
    except (OverflowError,struct.error):raise ValueError('Unrepresentable affine ground ceiling')
    if not math.isfinite(upper):raise ValueError('Unrepresentable affine ground ceiling')
    return expected+[source_margin],upper


def _source_finite_opaque_road_surface(certificate, xml, checked):
    """A source-oriented finite flat lane patch, never an infinite ground plane.

    rectangle_m binds its Native world envelope; the triangles retain the actual
    source heading, so an oblique road never becomes a filled bounding box.
    """
    reference = certificate.get('finite_opaque_road_surface')
    if reference is None:
        return None
    import json
    import numpy as np
    from .reference_geometry import ReferenceComponentGeometry, ReferenceActorGeometry
    source = json.loads(checked('finite-road-surface-qualification', reference).read_text())
    if (source.get('schema') != 'source_qualified_finite_flat_driving_surface_v1'
            or source.get('recording_id') != certificate['recording_id']
            or source.get('xodr_sha256') != certificate['xodr_sha256']
            or source.get('opaque_source_surface') is not True
            or source.get('lane_id') != -1):
        raise ValueError('Unqualified finite source road surface')
    refs = source.get('source_references', {})
    if not all(name in refs for name in ('geometry_generation', 'surface_opacity', 'source_binding')):
        raise ValueError('Missing finite road surface source contracts')
    _check_reference_dependencies(refs, checked,
        {r['sha256'] for r in certificate['original_sources'].values()})
    roads = [r for r in xml.findall('road') if r.get('id') == str(source.get('road_id'))]
    if len(roads) != 1:
        raise ValueError('Ambiguous finite road surface identity')
    road = roads[0]
    if road.findall('./lateralProfile/shape') or road.findall('./surface/*'):
        raise ValueError('Unsupported finite road surface shape')
    def number(node, key):
        value = float(node.attrib[key])
        if not math.isfinite(value):
            raise ValueError('Nonfinite road surface geometry')
        return value
    plans, sections = road.findall('./planView/geometry'), road.findall('./lanes/laneSection')
    if len(plans) != 1 or len(sections) != 1:
        raise ValueError('Finite road surface requires a single straight lane section')
    plan, section = plans[0], sections[0]
    if (plan.find('line') is None or len(list(plan)) != 1
            or number(plan, 's') != 0
            or number(plan, 'length') != number(road, 'length') or number(section, 's') != 0):
        raise ValueError('Unsupported finite road surface plan')
    for tag in ('elevation', 'superelevation', 'crossfall', 'laneOffset'):
        for node in road.iter(tag):
            if any(number(node, key) != 0 for key in ('a', 'b', 'c', 'd')):
                raise ValueError('Finite road surface is not flat and unshifted')
    lanes = [lane for lane in section.findall('right/lane') if lane.get('id') == '-1']
    if (len(lanes) != 1 or lanes[0].get('type') != 'driving'
            or lanes[0].get('level') != 'false' or lanes[0].findall('height')):
        raise ValueError('Unsupported finite driving lane surface')
    widths = lanes[0].findall('width')
    if (len(widths) != 1 or lanes[0].findall('border')
            or number(widths[0], 'sOffset') != 0
            or any(number(widths[0], key) != 0 for key in ('b', 'c', 'd'))):
        raise ValueError('Finite road surface requires constant source width')
    x, y = number(plan, 'x'), -number(plan, 'y')
    length, width = number(road, 'length'), number(widths[0], 'a')
    heading = number(plan, 'hdg'); c, s = math.cos(heading), math.sin(heading)
    axes = np.array([[c,-s,0.], [s,c,0.], [0.,0.,1.]])
    corners = np.array([[x,y], [x+c*length,y-s*length],
                        [x+c*length+s*width,y-s*length+c*width], [x+s*width,y+c*width]])
    envelope = [float(corners[:,0].min()), float(corners[:,0].max()),
                float(corners[:,1].min()), float(corners[:,1].max())]
    if length <= 0 or width <= 0 or source.get('rectangle_m') != envelope:
        raise ValueError('Finite road surface footprint differs from source')
    # Use a strict interior patch to cover source generator endpoint/Float32
    # rounding without extending the modeled road by any amount.
    inset = 64*2**-23*max(1., *(abs(v) for v in envelope))*(abs(c)+abs(s))
    if 2*inset >= min(length, width):
        raise ValueError('Insufficient finite road surface interior')
    x0, x1, y0, y1 = inset, length-inset, inset, width-inset
    model = ReferenceComponentGeometry(
        [[[x0,y0,0.], [x0,y1,0.], [x1,y0,0.]],
         [[x1,y0,0.], [x0,y1,0.], [x1,y1,0.]]],
        np.empty((0,3)), np.empty((0,3)), np.empty((0,3)), np.empty(0), 0.)
    model.qualify_opaque_triangles(np.arange(2))
    model.qualify_single_sided_triangles(np.arange(2))
    return ReferenceActorGeometry(model, [x,y,0.], axes,
        64*2**-52*max(1., *(abs(v) for v in envelope)))


def _analytic_segment_ground_clearance(observer, target, ceiling, ground_plane=None):
    """A linear signed-height function attains its segment minimum at an endpoint."""
    from .road_visibility_geometry import FlatRoadInterior
    if isinstance(ground_plane,FlatRoadInterior):return ground_plane.clearance(observer,target)
    if ground_plane is None:return min(observer[2],target[2])-ceiling
    gx,gy,z0,source_margin=ground_plane
    signed=[p[2]-gx*p[0]-gy*p[1]-z0 for p in (observer,target)]
    # Whole-source roadmesh construction residual is mandatory: mesh vertices
    # need not lie in the segment coordinate box. Also cover query endpoints
    # and widen the binary64 signed-height evaluation.
    scale=max(1.,abs(z0),*(abs(v)for p in (observer,target)for v in p))
    margin=max(source_margin,64*2**-23*scale*(1+abs(gx)+abs(gy)))+64*2**-52*scale*(1+abs(gx)+abs(gy))
    return min(signed)-margin


def _generation_source_key(certificate):
    from pathlib import PurePosixPath
    key=certificate.get('generation_source_key','runner.py')
    if (not isinstance(key,str) or not key or PurePosixPath(key).is_absolute()
            or '..' in PurePosixPath(key).parts):
        raise ValueError('Invalid original generation source key')
    return key


def _source_assigned_generation_parameters(tree, constructor, height, originals):
    """Qualify a consecutive literal SDK-parameter block and native map readback."""
    import ast, hashlib, json
    from pathlib import Path
    if constructor.args or constructor.keywords:
        raise ValueError('Assigned generation parameters require an empty SDK constructor')
    imports=[a for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names
             if (a.asname or a.name.split('.')[0])=='carla']
    if (not isinstance(constructor.func.value,ast.Name) or constructor.func.value.id!='carla'
            or len(imports)!=1 or imports[0].name!='carla' or imports[0].asname is not None
            or any(isinstance(n,ast.ImportFrom) and any((a.asname or a.name)=='carla' for a in n.names)
                   or isinstance(n,ast.Name) and n.id=='carla' and isinstance(n.ctx,(ast.Store,ast.Del))
                   or isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name=='carla'
                   or isinstance(n,ast.Attribute) and n.attr=='OpendriveGenerationParameters'
                   and isinstance(n.ctx,ast.Store) for n in ast.walk(tree))):
        raise ValueError('Generation parameter SDK namespace is not source-bound')
    matches=[(i,n) for i,n in enumerate(tree.body) if isinstance(n,ast.Assign)
             and n.value is constructor and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)]
    if len(matches)!=1:raise ValueError('Generation parameters are not one top-level local object')
    index,binding=matches[0];name=binding.targets[0].id
    allowed={'wall_height','additional_width','vertex_distance','max_road_length',
             'smooth_junctions','enable_mesh_visibility','enable_pedestrian_navigation'}
    boolean={'smooth_junctions','enable_mesh_visibility','enable_pedestrian_navigation'}
    values={};uses=set();cursor=index+1
    while cursor<len(tree.body):
        node=tree.body[cursor]
        if not (isinstance(node,ast.Assign) and len(node.targets)==1
                and isinstance(node.targets[0],ast.Attribute)
                and isinstance(node.targets[0].value,ast.Name) and node.targets[0].value.id==name):break
        target=node.targets[0];value=node.value
        if target.attr not in allowed or target.attr in values or not isinstance(value,ast.Constant):
            raise ValueError('Unknown, repeated or nonliteral generation parameter assignment')
        if target.attr in boolean:
            valid=type(value.value)is bool
        else:
            valid=type(value.value)in(int,float) and math.isfinite(value.value) and value.value>=0
            if target.attr in ('vertex_distance','max_road_length'):valid=valid and value.value>0
        if not valid:raise ValueError('Invalid literal generation parameter value')
        values[target.attr]=value.value;uses.add(id(target.value));cursor+=1
    if values.get('wall_height')!=height:
        raise ValueError('Assigned wall height differs from analytical source')
    if cursor>=len(tree.body):raise ValueError('Missing local-parameter world generation')
    generated=tree.body[cursor]
    if not (isinstance(generated,ast.Assign) and len(generated.targets)==1
            and isinstance(generated.targets[0],ast.Name) and isinstance(generated.value,ast.Call)):
        raise ValueError('Ambiguous local-parameter world generation')
    call=generated.value
    if not (isinstance(call.func,ast.Attribute) and call.func.attr=='generate_opendrive_world'
            and len(call.args)==2 and not call.keywords and isinstance(call.args[0],ast.Name)
            and isinstance(call.args[1],ast.Name) and call.args[1].id==name):
        raise ValueError('Local parameters do not bind the recorded-world call')
    if sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
           and n.func.attr=='generate_opendrive_world' for n in ast.walk(tree))!=1:
        raise ValueError('Ambiguous local-parameter generation calls')
    uses.add(id(call.args[1]))
    if any(isinstance(n,ast.Name) and n.id==name and
           (isinstance(n.ctx,ast.Store) and n is not binding.targets[0]
            or isinstance(n.ctx,ast.Load) and id(n)not in uses) for n in ast.walk(tree)):
        raise ValueError('Generation parameter object escapes or is rebound')
    if cursor+1>=len(tree.body):raise ValueError('Missing generated-world map readback')
    readback=tree.body[cursor+1]
    expected=generated.targets[0].id+'.get_map().to_opendrive()'
    expression=readback.value if isinstance(readback,ast.Assign) else None
    # Compare AST structure, independent of whitespace and Python's unparse availability.
    if expression is None or ast.dump(expression)!=ast.dump(ast.parse(expected,mode='eval').body):
        raise ValueError('Map readback is not from the generated world')
    if not {'road.xodr','physical_geometry.json'}<=set(originals):
        raise ValueError('Assigned generation lacks retained native map identity')
    geometry=json.loads(Path(originals['physical_geometry.json']).read_text())
    if geometry.get('map_sha256')!=hashlib.sha256(Path(originals['road.xodr']).read_bytes()).hexdigest():
        raise ValueError('Assigned generation native map identity differs')


def _source_generated_opaque_ceiling(certificate, originals, source_contracts=None):
    """Read the actual generation wall parameter without executing source code."""
    import ast,json
    from pathlib import Path
    def key(node):
        value=node.slice
        if isinstance(value,ast.Index):value=value.value
        return value.value if isinstance(value,ast.Constant)else None
    height=certificate.get('generation_parameters',{}).get('wall_height')
    ceiling=certificate.get('opaque_geometry_global_upper_z_m')
    if (type(height)not in(int,float)or not math.isfinite(height)or height<0
            or type(ceiling)not in(int,float)or not math.isfinite(ceiling)):
        raise ValueError('Invalid analytical geometry ceiling')
    expected = height
    if 'road.xodr' in originals:
        import xml.etree.ElementTree as ET
        xml = ET.parse(originals['road.xodr']).getroot()
        if 'reference_ground_plane' in certificate:
            _,upper=_source_reference_ground_plane(xml,certificate['reference_ground_plane'],height)
            elevated=True
        else:elevated,upper=_constant_native_ground_ceiling(xml)
        if elevated:
            import hashlib
            required={'Map.cpp':'c123ab21ad8770d42824660ab8f50bc2045a95b16277a026aeaef3ad0667f209',
                      'MeshFactory.cpp':'24984f06eccd8d11ed91d89f939a7a544e6866fbfa5883e7901b48904243ae14'}
            if height!=0:
                raise ValueError('Unsupported combined elevated wall/sidewalk geometry')
            for name,source_hash in required.items():
                path=(source_contracts or {}).get(name)
                if path is None or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=source_hash:
                    raise ValueError('Unqualified constant-elevation generator source')
            expected=upper
        if any(lane.get('type') == 'sidewalk' for lane in xml.findall('./road/lanes/laneSection/*/lane')):
            import hashlib, struct
            lane_source = (source_contracts or {}).get('Lane.cpp')
            if (height != 0 or lane_source is None
                    or hashlib.sha256(Path(lane_source).read_bytes()).hexdigest()
                    != '53adedca967bf6e617bc47b861307a37e831baa604f0fae165577deec1704289'):
                raise ValueError('Unqualified native sidewalk reference geometry')
            curb=struct.unpack('!f',struct.pack('!f',.1524))[0]
            expected=_constant_native_ground_ceiling(xml,curb)[1]if elevated else curb
    if ceiling != expected:
        raise ValueError('Analytical ceiling differs from qualified generated geometry')
    source_key=_generation_source_key(certificate)
    if source_key not in originals:raise ValueError('Missing original generation source: '+source_key)
    tree=ast.parse(Path(originals[source_key]).read_text())
    calls=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)
           and n.func.attr=='OpendriveGenerationParameters']
    if not calls:
        import hashlib
        required={'Client.cpp':'999e69519ca8bc75ae056f27b154d821aebc0f83d4ff9c396c703a17666e8b4f',
                  'OpendriveGenerationParameters.h':'554dad71561dae0a099cba49863c28f5cdac2d6ddd6fe7d088ae44daea857aee'}
        for name,expected_hash in required.items():
            path=(source_contracts or {}).get(name)
            if path is None or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected_hash:
                raise ValueError('Unqualified SDK default generation source')
        generated=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='generate_opendrive_world']
        if len(generated)!=1 or len(generated[0].args)!=1 or generated[0].keywords:
            raise ValueError('Ambiguous or overridden SDK default generation parameters')
        if height!=1.:raise ValueError('Analytical wall height differs from original SDK default')
        return ceiling
    if len(calls)!=1:raise ValueError('Ambiguous original OpenDRIVE generation parameters')
    values={k.arg:k.value for k in calls[0].keywords}
    wall=values.get('wall_height')
    if wall is None:
        _source_assigned_generation_parameters(tree,calls[0],height,originals)
    elif isinstance(wall,ast.Constant)and type(wall.value)in(int,float):
        if wall.value!=height:raise ValueError('Analytical wall height differs from original literal source')
    elif (isinstance(wall,ast.Subscript)and isinstance(wall.value,ast.Name)and wall.value.id=='c'
          and key(wall)=='curb_height_m'):
        if not {'config.json','setup_geometry.json'}<=set(originals):
            raise ValueError('Parameterized wall height lacks original configuration/setup')
        config=json.loads(Path(originals['config.json']).read_text())
        setup=json.loads(Path(originals['setup_geometry.json']).read_text())
        declared=config.get('construction',{}).get('curb_height_m')
        if (type(declared)not in(int,float)or declared!=height or setup.get('curb_height_m')!=height
                or not setup.get('curb_face_queries')or not setup.get('top_surface_queries')):
            raise ValueError('Analytical wall height disagrees with retained configuration/setup')
        if not any(isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='c'for t in n.targets)
                   and isinstance(n.value,ast.Subscript)and isinstance(n.value.value,ast.Name)
                   and n.value.value.id=='cfg'and key(n.value)=='construction'for n in ast.walk(tree)):
            raise ValueError('Unqualified generation configuration binding')
    elif isinstance(wall,ast.Name):
        # A pure local parameter factory, bound at the recorded-world call.
        helpers=[f for f in ast.walk(tree) if isinstance(f,ast.FunctionDef)
                 and len(f.body)==1 and isinstance(f.body[0],ast.Return)
                 and f.body[0].value is calls[0] and len(f.args.args)==1
                 and f.args.args[0].arg==wall.id and not f.args.defaults
                 and not f.args.kwonlyargs and f.args.vararg is None
                 and f.args.kwarg is None]
        if len(helpers)!=1:raise ValueError('Unqualified generation parameter factory')
        helper=helpers[0]
        if (getattr(helper.args,'posonlyargs',[])
                or sum(isinstance(n,ast.FunctionDef)and n.name==helper.name
                       for n in ast.walk(tree))!=1
                or any(isinstance(n,ast.Name)and isinstance(n.ctx,ast.Store)
                       and n.id==helper.name for n in ast.walk(tree))):
            raise ValueError('Ambiguous generation parameter factory binding')
        generated=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Attribute)and n.func.attr=='generate_opendrive_world'
                   and len(n.args)==2 and not n.keywords
                   and isinstance(n.args[0],ast.Subscript)
                   and isinstance(n.args[0].value,ast.Name)and n.args[0].value.id=='cfg'
                   and key(n.args[0])=='map_xml']
        if len(generated)!=1:raise ValueError('Ambiguous recorded-world generation')
        invocation=generated[0].args[1]
        if (not isinstance(invocation,ast.Call)or not isinstance(invocation.func,ast.Name)
                or invocation.func.id!=helper.name or len(invocation.args)!=1
                or invocation.keywords or not isinstance(invocation.args[0],ast.Constant)
                or type(invocation.args[0].value)not in(int,float)
                or invocation.args[0].value!=height):
            raise ValueError('Wall parameter differs from recorded-world factory argument')
        if not {'config.json','setup_geometry.json','road.xodr'}<=set(originals):
            raise ValueError('Factory-bound generation lacks original config/setup/map')
        import hashlib
        config=json.loads(Path(originals['config.json']).read_text())
        setup=json.loads(Path(originals['setup_geometry.json']).read_text())
        map_hash=hashlib.sha256(Path(originals['road.xodr']).read_bytes()).hexdigest()
        if (not isinstance(config.get('map_xml'),str)
                or hashlib.sha256(config['map_xml'].encode()).hexdigest()!=map_hash
                or setup.get('map_sha256')!=map_hash
                or setup.get('generation_parameters',{}).get('wall_height')!=height
                or height > 0 and not _source_curb_face_queries(originals,setup)):
            raise ValueError('Factory-bound source generation disagrees with retained setup')
    else:raise ValueError('Unsupported original wall-height expression')
    return ceiling


def _source_curb_face_queries(originals, setup):
    """Read equivalent original native probes without changing source bytes.

    Callers supply only hash-verified Evidence/original-source paths.
    A separate producer channel records positions, not object bounding boxes.
    """
    import ast, hashlib, json
    from pathlib import Path
    def normalize(rows, separate):
        if not isinstance(rows, list) or not rows:
            raise ValueError('Missing native curb-face probes')
        result=[]
        for row in rows:
            if not isinstance(row,dict) or any((separate or k in row) and (type(row.get(k))not in(int,float) or not math.isfinite(row[k])) for k in('x_m','y_m')):
                raise ValueError('Invalid native curb-face query coordinates')
            hits=row.get('hits_native_m' if separate else 'hits')
            if not isinstance(hits,list) or not hits:
                raise ValueError('Missing native curb-face hit positions')
            positions=hits if separate else [h.get('position_native_m') if isinstance(h,dict) else None for h in hits]
            if any(not _finite_vector(p) for p in positions):
                raise ValueError('Invalid native curb-face hit positions')
            result.append({'x_m':row.get('x_m'),'y_m':row.get('y_m'),'hits':[{'position_native_m':p} for p in positions]})
        return result
    embedded=normalize(setup['curb_face_queries'],False) if 'curb_face_queries'in setup else None
    source=originals.get('curb-native-probe.json')
    if source is None:return embedded or []
    if not {'runner.py','config.json','road.xodr'}<=set(originals):
        raise ValueError('Separate curb probes lack original source/map contract')
    config=json.loads(Path(originals['config.json']).read_text())
    digest=hashlib.sha256(Path(originals['road.xodr']).read_bytes()).hexdigest()
    if not isinstance(config.get('map_xml'),str) or hashlib.sha256(config['map_xml'].encode()).hexdigest()!=digest or setup.get('map_sha256')!=digest:
        raise ValueError('Separate curb probes disagree with original source map')
    tree=ast.parse(Path(originals['runner.py']).read_text())
    # Require the native-location serialization and original output channel,
    # not a similarly named JSON file containing arbitrary coordinates.
    serializers=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='xyz']
    if len(serializers)!=1 or not isinstance(serializers[0],ast.FunctionDef):
        raise ValueError('Unqualified native XYZ serialization')
    serializer=serializers[0]
    if (len(serializer.args.args)!=1 or serializer.args.vararg or serializer.args.kwarg or serializer.args.kwonlyargs or serializer.args.defaults or serializer.decorator_list or len(serializer.body)!=1 or not isinstance(serializer.body[0],ast.Return)):
        raise ValueError('Unqualified native XYZ serialization')
    argument=serializer.args.args[0].arg
    expected=ast.parse('[float('+argument+'.x),float('+argument+'.y),float('+argument+'.z)]',mode='eval').body
    if ast.dump(serializer.body[0].value)!=ast.dump(expected) or any(isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id in('xyz','float') for n in ast.walk(tree)):
        raise ValueError('Transformed or rebound native XYZ serialization')
    writes=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write' and len(n.args)==2 and isinstance(n.args[0],ast.BinOp) and isinstance(n.args[0].op,ast.Div) and isinstance(n.args[0].right,ast.Constant) and n.args[0].right.value=='curb-native-probe.json']
    records=[n for n in ast.walk(tree) if isinstance(n,ast.Dict) and any(isinstance(k,ast.Constant) and k.value=='hits_native_m' and isinstance(value,ast.ListComp) and isinstance(value.elt,ast.Call) and isinstance(value.elt.func,ast.Name) and value.elt.func.id=='xyz' and len(value.elt.args)==1 and isinstance(value.elt.args[0],ast.Attribute) and value.elt.args[0].attr=='location' for k,value in zip(n.keys,n.values))]
    rays=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='cast_ray']
    if len(writes)!=1 or len(records)!=1 or not rays:
        raise ValueError('Unqualified separate native curb-probe producer')
    output=writes[0].args[1]
    appends=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='append' and isinstance(n.func.value,ast.Name) and isinstance(output,ast.Name) and n.func.value.id==output.id and n.args==[records[0]]]
    values=[value for key,value in zip(records[0].keys,records[0].values) if isinstance(key,ast.Constant) and key.value=='hits_native_m']
    comp=values[0]
    if len(comp.generators)!=1 or not isinstance(comp.generators[0].iter,ast.Name):
        raise ValueError('Unqualified separate native curb-probe data flow')
    generator=comp.generators[0]
    if (not isinstance(generator.target,ast.Name) or generator.ifs or generator.is_async or not isinstance(comp.elt.args[0].value,ast.Name) or comp.elt.args[0].value.id!=generator.target.id):
        raise ValueError('Unqualified native hit coordinate semantics')
    hitname=generator.iter.id
    initial=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and isinstance(output,ast.Name) and t.id==output.id for t in n.targets)]
    if len(initial)!=1 or not isinstance(initial[0].value,ast.List) or initial[0].value.elts:
        raise ValueError('Ambiguous separate curb-probe output assignment')
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id==hitname]
    worlds=[n.targets[0].id for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='generate_opendrive_world' and n.value.args and isinstance(n.value.args[0],ast.Subscript)]
    if (len(appends)!=1 or len(assignments)!=1 or assignments[0].value not in rays or not isinstance(assignments[0].value.func.value,ast.Name) or assignments[0].value.func.value.id not in worlds):
        raise ValueError('Unqualified separate native curb-probe data flow')
    separate=normalize(json.loads(Path(source).read_text()),True)
    if embedded is not None and embedded!=separate:
        raise ValueError('Conflicting original curb-face probe sources')
    return separate


def _native_branch_nodes(inventory, map_digest, frames_digest, route_digest):
    """Read independently queried Native results, not the proof's own options."""
    if (inventory.get('schema') != 'source_sdk_native_predecessor_inventory_v1'
            or inventory.get('map', {}).get('sha256') != map_digest
            or inventory.get('retained_frames', {}).get('sha256') != frames_digest
            or inventory.get('route_module', {}).get('sha256') != route_digest
            or inventory.get('distance_m') != .001
            or inventory.get('no_simulator_connection') is not True):
        raise ValueError('Unqualified independent native branch inventory')
    nodes = {}
    for node in inventory.get('nodes', []):
        endpoint = tuple(node['endpoint'])
        options = node['actual_native_alternatives']
        if (len(endpoint) != 4 or endpoint in nodes or len(options) < 2
                or len({tuple(value) for value in options}) != len(options)):
            raise ValueError('Incomplete independent native branch inventory')
        nodes[endpoint] = options
    if inventory.get('independently_queried_native_endpoints') != len(nodes):
        raise ValueError('Independent native branch endpoint count differs')
    return nodes


def _analytic_supplement_identity(supplement, recording_id, packet_digest, certificate_digest, frames_digest):
    if (supplement.get('schema') != 'source_bound_analytic_visibility_supplement_v1'
            or supplement.get('recording_id') != recording_id
            or supplement.get('packet_sha256') != packet_digest
            or supplement.get('certificate_sha256') != certificate_digest
            or supplement.get('retained_frames_sha256') != frames_digest):
        raise ValueError('Analytical supplement source identity differs')


def _native_branch_paths(lane, nodes):
    """Require every native alternative at every encountered branch prefix."""
    paths = lane.get('enumerated_actual_native_paths')
    if not isinstance(paths, list) or not 1 <= len(paths) <= 64:
        raise ValueError('Incomplete native branch paths')
    prefixes, leaves = {}, set()
    for path in paths:
        choices = path.get('branch_choices')
        if path.get('complete') is not True or not choices or len(choices) > 16:
            raise ValueError('Incomplete native branch path')
        prefix = ()
        for choice in choices:
            endpoint = tuple(choice['source_endpoint'])
            actual = nodes.get(endpoint)
            selected = choice.get('selected_index_in_this_enumerated_path')
            if (actual is None or choice.get('actual_Native_previous_alternatives') != actual
                    or type(selected) is not int or not 0 <= selected < len(actual)):
                raise ValueError('Branch options differ from independently queried Native')
            if prefix in prefixes and prefixes[prefix] != endpoint:
                raise ValueError('Conflicting native branch prefixes')
            prefixes[prefix] = endpoint
            prefix += (selected,)
        if prefix in leaves:
            raise ValueError('Duplicate native branch path')
        leaves.add(prefix)
    def complete(prefix):
        if prefix in leaves:
            if prefix in prefixes:
                raise ValueError('Truncated native branch path')
            return
        if prefix not in prefixes:
            raise ValueError('Missing actual native branch alternative')
        for selected in range(len(nodes[prefixes[prefix]])):
            complete(prefix + (selected,))
    complete(())
    return paths


def _analytic_route_samples(route, observations, distances, samples, ceiling, eye, maximum, map_digest, enclosures=(), native_positions=None, ground_plane=None):
    if (route.get('method') != ROUTE_METHOD or route.get('unknown_reason')
            or route.get('map_sha256') != map_digest or route.get('topology_available') is not True
            or route.get('maximum_route_distance_m', -1) < maximum
            or len(observations) != len(distances)
            or any(abs(a['distance_m'] - b) > 1e-8 for a, b in zip(observations, distances))):
        raise ValueError('Analytical route/search coverage incomplete')
    if native_positions is not None and len(native_positions) != len(observations):
        raise ValueError('Incomplete independent native observer queries')
    for position_index, sample in enumerate(observations):
        observer, indices = sample['observer_m'], sample['clear_sample_indices']
        clearance = sample['minimum_proved_vertical_clearance_m']
        if (not _finite_vector(observer) or not indices or len(indices) != len(set(indices))
                or any(type(i) is not int or not 0 <= i < 9 for i in indices)):
            raise ValueError('Invalid analytical segment witnesses')
        if native_positions is not None:
            expected = list(native_positions[position_index]); expected[2] += eye
            if math.dist(observer, expected) > 1e-6:
                raise ValueError('Observer differs from independent native source query')
        if any(_segment_intersects_enclosure(observer, samples[i], box) for i in indices for box in enclosures):
            raise ValueError('Claimed clear sample intersects a qualified opaque enclosure')
        gaps = [_analytic_segment_ground_clearance(observer,samples[i],ceiling,ground_plane) for i in indices]
        if (min(gaps) <= 0 or type(clearance) not in (int, float) or not math.isfinite(clearance)
                or not 0 < clearance <= max(gaps) + 1e-8):
            raise ValueError('Analytical segment is below the complete geometry ceiling')
        terminal, distance = route.get('terminal'), sample['distance_m']
        if terminal is not None and distance >= terminal['in_domain_distance_m']:
            expected = [p + (distance - terminal['in_domain_distance_m']) * u
                        for p, u in zip(terminal['position_m'], terminal['upstream_unit_tangent_3d'])]
            expected[2] += eye
            if math.dist(observer, expected) > .001:
                raise ValueError('Analytical observer differs from terminal route')


def _analytic_row_blocked(row, samples, event, enclosures):
    points = [point for participant in event['participants']
              for point in participant['body_vertices_m']+[participant['position_m']]]
    observer = row['observer_m']
    margin = 64*2**-23*max(1., *(abs(x) for point in points+[observer] for x in point))
    models = [box['_source_reference_components'] for box in enclosures
              if '_source_reference_components' in box]
    return all(any(model.proves_opaque_hit(observer, target, margin)
                   for model in models) for target in samples)


def _analytic_first_loss_lane(lane, distances, samples, event, ceiling, eye,
                              maximum, probe, tolerance, map_digest, enclosures,
                              native_positions, ground_plane):
    """Verify a refined first sampled loss, including the complete clear prefix.

    A source-qualified opaque face can prove blockage. An enclosing box cannot.
    Refinement uses a complete fine subscan, so a later clear section never
    replaces an earlier sampled loss. This is not a continuous optical cutoff.
    """
    observations, route = lane['sample_certificates'], lane['route']
    bracket, initial, fine_step = (lane.get(k) for k in
        ('bracket_m', 'initial_occlusion_m', 'refinement_step_m'))
    origin_blocked = initial == 0 and bracket == [0, 0]
    lower_basis = lane.get('lower_bound_basis')
    origin_bound = (lower_basis == 'nonnegative_route_distance'
                    and isinstance(bracket,list) and len(bracket)==2
                    and bracket[0]==0 and type(bracket[1])in(int,float)
                    and bracket[1]>0 and initial==bracket[1])
    if lower_basis is not None and not origin_bound:
        raise ValueError('Invalid nonnegative origin lower-bound proof')
    if (not isinstance(bracket, list) or len(bracket) != 2
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   for x in bracket+[initial, fine_step])
            or not 0 < fine_step <= tolerance or (initial not in distances and not origin_bound)
            or (initial == 0 and not origin_blocked)
            or not 0 <= bracket[0] <= initial
            or not (bracket[0] < bracket[1] <= maximum or origin_blocked)
            or bracket[1]-bracket[0] > tolerance+1e-9):
        raise ValueError('Invalid analytical first-loss refinement')
    fine_count = math.ceil(initial/fine_step)+1
    if fine_count > len(observations):
        raise ValueError('Incomplete analytical first-loss subscan')
    expected = sorted(set(distances+[min(k*fine_step, initial)
        for k in range(fine_count)]+[initial]+bracket))
    observed = [row.get('distance_m') for row in observations]
    if (native_positions is None or len(native_positions) != len(observations)
            or any(type(d) not in (int, float) or not math.isfinite(d)
                   or not 0 <= d <= maximum for d in observed)
            or any(a >= b for a, b in zip(observed, observed[1:]))
            or any(not any(abs(d-x) <= 1e-8 for x in observed) for d in expected)):
        raise ValueError('Incomplete analytical first-loss subscan or native queries')
    low, high = bracket
    # Additional boundary probes may enclose an unresolved sample. It remains
    # inside the declared uncertainty bracket; every sample through the lower
    # endpoint must still prove clear, and the upper endpoint must prove blocked.
    def blocked(row):
        return _analytic_row_blocked(row, samples, event, enclosures)
    selected, positions = [], []
    for row, native in zip(observations, native_positions):
        observer = row['observer_m']
        expected_eye = list(native); expected_eye[2] += eye
        if not _finite_vector(observer) or math.dist(observer, expected_eye) > 1e-6:
            raise ValueError('First-loss observer differs from independent native query')
        # A nine-ray loss at the origin has an empty clear prefix of length0;
        # it never supplies a fictitious clear observation at distance0.
        if origin_bound and row['distance_m']==0 and (row.get('clear_sample_indices') or blocked(row)):
            raise ValueError('Nonnegative bound must preserve the unresolved origin observation')
        if (row['distance_m'] <= low and not(origin_blocked or origin_bound)) or row['distance_m'] == probe:
            if row.get('clear_sample_indices'):
                selected.append(row); positions.append(native)
            elif row['distance_m'] <= low:
                raise ValueError('Unknown observation in required first-loss clear prefix or probe')
        if row['distance_m'] == high and (row.get('clear_sample_indices') or not blocked(row)):
            raise ValueError('First sampled loss lacks nine qualified opaque-hit proofs')
    _analytic_route_samples(route, selected, [r['distance_m'] for r in selected],
        samples, ceiling, eye, maximum, map_digest, enclosures, positions, ground_plane)
    probe_row = next(row for row in observations if row['distance_m'] == probe)
    result = {'lane_id': lane['lane_id'], 'observer_route': route,
        'any_body_sight_horizon': {'bound': 'first_sampled_occlusion', 'bracket_m': bracket},
        'analytic_sample_certificates': observations,
        'source_opacity_convention': 'asset_uv0_base_mip_bilinear_matte_v1'}
    if origin_bound:
        result['lower_bound_basis']='nonnegative_route_distance'
        result['origin_visibility']='unknown'
    if probe_row.get('clear_sample_indices'):
        result['any_sample_clear_at_probe'] = True
    elif blocked(probe_row):
        result['any_sample_clear_at_probe'] = False
    else:
        result['probe_unknown_reason'] = 'No qualified clear or opaque-hit proof at later probe'
    return result


def _minimum_path_horizon(paths, tolerance, require_resolved_minimum=True):
    """Retain every path; an unfinished tail must not affect the finite minimum."""
    lowers, uppers, unfinished = [], [], []
    for path in paths:
        horizon = path['any_body_sight_horizon']
        if horizon['bound'] == 'first_sampled_occlusion':
            low, high = horizon['bracket_m']
            lowers.append(low); uppers.append(high)
        else:
            lowers.append(horizon['distance_m'])
        if path.get('search_tail_unresolved'):
            unfinished.append(lowers[-1])
    if unfinished and (not uppers or any(low < min(uppers) for low in unfinished)):
        if require_resolved_minimum:
            raise ValueError('Unfinished native path can change the minimum sight horizon')
        return {'bound': 'at_least', 'distance_m': min(lowers)}
    if uppers:
        bracket = [min(lowers), min(uppers)]
        if bracket[1]-bracket[0] > tolerance+1e-9:
            raise ValueError('Unrefined minimum native path horizon')
        return {'bound': 'first_sampled_occlusion', 'bracket_m': bracket}
    return {'bound': 'at_least', 'distance_m': min(lowers)}


def _analytic_clear_prefix(path, observations, distances, samples, ceiling, eye,
                           maximum, probe, tolerance, map_digest, enclosures,
                           native_positions, ground_plane):
    """Verify the full declared clear prefix without claiming its unknown tail."""
    lower, step = path.get('clear_prefix_distance_m'), path.get('refinement_step_m')
    if (type(lower) not in (int, float) or not math.isfinite(lower)
            or not 0 <= lower < maximum or type(step) not in (int, float)
            or not math.isfinite(step) or not 0 < step <= tolerance
            or path.get('search_limit_m') != maximum
            or path.get('unresolved_tail') is not True):
        raise ValueError('Uncertified native clear prefix')
    observed = [row['distance_m'] for row in observations]
    count = math.ceil(lower/step)+1
    if native_positions is None or count > len(observations):
        raise ValueError('Incomplete native clear-prefix sampling')
    expected = sorted(set(distances+[min(k*step, lower)
        for k in range(count)]+[lower]))
    if (len(observations) != len(native_positions)
            or any(a >= b for a, b in zip(observed, observed[1:]))
            or any(type(d) not in (int, float) or not math.isfinite(d)
                   or not 0 <= d <= maximum for d in observed)
            or any(not any(abs(d-x) <= 1e-8 for x in observed) for d in expected)):
        raise ValueError('Incomplete native clear-prefix sampling')
    for row, position in zip(observations, native_positions):
        expected_eye = list(position); expected_eye[2] += eye
        if not _finite_vector(row['observer_m']) or math.dist(row['observer_m'], expected_eye) > 1e-6:
            raise ValueError('Clear-prefix observer differs from independent native query')
    selected = [(row, position) for row, position in zip(observations, native_positions)
                if row['distance_m'] <= lower]
    _analytic_route_samples(path['provenance'], [row for row, _ in selected],
        [row['distance_m'] for row, _ in selected], samples, ceiling, eye,
        maximum, map_digest, enclosures, [p for _, p in selected], ground_plane)
    return {'bound': 'at_least', 'distance_m': lower}


def _source_nonrendered_object_declarations(xml, source_contracts):
    """The pinned standalone path does not render these XML road objects.

    GenerateAll -> GenerateRoadMesh -> Map::GenerateChunkedMesh uses the
    lane/wall MeshFactory path. Map::GetAllCrosswalkMesh is a separate API.
    The pinned ObjectParser also ignores roadMark objects named StopLine.
    This says nothing about spawned marking actors: their complete Native
    inventory and source-qualified enclosures are checked independently.
    """
    import hashlib
    from pathlib import Path
    objects = xml.findall('./road/objects/*')
    if not objects: return
    for obj in objects:
        if (obj.tag != 'object' or not (obj.get('type') == 'crosswalk'
                or obj.get('type') == 'roadMark' and obj.get('name') == 'StopLine')
                or float(obj.get('height', '0')) != 0.
                or any(float(c.get('z', '0')) != 0. for c in obj.findall('./outline/cornerLocal'))):
            raise ValueError('Unsupported additional object declarations')
    required = {
        'OpenDriveGenerator.cpp': 'aa55d2967c7c01796bd277e8fb64bd7b4a85a67e5104bdec9ba4790456deb2ff',
        'Map.cpp': 'c123ab21ad8770d42824660ab8f50bc2045a95b16277a026aeaef3ad0667f209',
        'MeshFactory.cpp': '24984f06eccd8d11ed91d89f939a7a544e6866fbfa5883e7901b48904243ae14'}
    if any(obj.get('type') == 'roadMark' for obj in objects):
        required['ObjectParser.cpp'] = '50bb48a06890f73811261d9823db9460e28ba8a0f0521b96a6aae1a03ff35e4a'
    for name, expected in required.items():
        path = source_contracts.get(name)
        if path is None or hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Unqualified standalone object generation source: ' + name)


def load_analytic_reference_visibility(packet_path, certificate_path, frames_path, source_resolver=None, supplement_path=None):
    """Verify retained proof inputs once, then reuse the normal sight attachment.

    This source path checks clear segments above qualified generated road
    geometry and outside every source-qualified opaque actor enclosure.
    It never represents a new simulator ray cast.
    source_resolver(name, ref) supports hash-verified relocation on publication.
    """
    import hashlib,json
    from pathlib import Path
    import xml.etree.ElementTree as ET
    def digest(path):
        h=hashlib.sha256()
        with Path(path).open('rb')as f:
            for data in iter(lambda:f.read(1048576),b''):h.update(data)
        return h.hexdigest()
    def checked(name, reference):
        path=Path(source_resolver(name,reference) if source_resolver else reference['path'])
        if not path.is_file() or digest(path)!=reference['sha256']:
            raise ValueError('Analytical visibility source hash mismatch: '+name)
        return path
    packet=json.loads(Path(packet_path).read_text());certificate=json.loads(Path(certificate_path).read_text());table=json.loads(Path(frames_path).read_text())
    packet_digest,certificate_digest,frames_digest=digest(packet_path),digest(certificate_path),digest(frames_path)
    if (packet.get('schema')!='derived_source_bound_analytic_body_visibility_v1' or packet.get('method')!=ANALYTIC_METHOD
            or packet.get('estimate')is not True or packet.get('no_cast_ray_executed')is not True):
        raise ValueError('Unknown analytical visibility source method')
    if certificate_digest!=packet['source_certificate']['sha256'] or frames_digest!=packet['source_frames']['sha256']:
        raise ValueError('Analytical visibility certificate/frame binding differs')
    if (certificate.get('schema')!='standalone_opendrive_source_bound_certificate_v1'
            or certificate.get('source_model')!='standalone_opendrive_collision_reference_geometry'
            or certificate.get('complete_existing_opaque_scene_qualified')is not True
            or certificate.get('target_self_bbox_excluded')is not True
            or certificate.get('no_new_world_objects')is not True or certificate.get('no_scene_amendment')is not True
):
        raise ValueError('Unsupported or incomplete analytical scene certificate')
    if packet['recording_id']!=certificate['recording_id'] or table['recording_id']!=packet['recording_id']:
        raise ValueError('Analytical visibility recording identity differs')
    originals={name:checked(name,reference)for name,reference in certificate['original_sources'].items()}
    supplement = None
    supplement_digest = None
    branch_frames, native_nodes, inventory = {}, {}, None
    if supplement_path is not None:
        supplement = json.loads(Path(supplement_path).read_text())
        supplement_digest = digest(supplement_path)
        _analytic_supplement_identity(supplement, packet['recording_id'], packet_digest, certificate_digest, frames_digest)
        for name, reference in supplement.get('additional_original_sources', {}).items():
            if name != 'capture/native_map_facts.json' or name in originals:
                raise ValueError('Unsupported or conflicting additional original source')
            originals[name] = checked(name, reference)
        branch_proof = json.loads(checked('native-branch-proof.json', supplement['branch_proof']).read_text())
        inventory = json.loads(checked('native-alternatives.json', supplement['native_alternative_inventory']).read_text())
        if (branch_proof.get('recording_id') != packet['recording_id']
                or branch_proof.get('source_certificate_sha256') != certificate_digest
                or inventory.get('recording_id') != packet['recording_id']):
            raise ValueError('Native branch proof source identity differs')
        for name in ('map', 'retained_frames', 'route_module', 'qualifier_source'):
            checked('native-inventory-' + name, inventory[name])
        native_nodes = _native_branch_nodes(inventory, certificate['xodr_sha256'], frames_digest, packet['route_module']['sha256'])
        for branch_frame in branch_proof['all_native_branch_frame_results']:
            ident = branch_frame['original_frame']
            if ident in branch_frames or branch_frame.get('complete_all_paths') is not True:
                raise ValueError('Duplicate or incomplete native branch frame')
            branch_frames[ident] = branch_frame
        if branch_proof.get('newly_qualified_branch_frames') != len(branch_frames):
            raise ValueError('Native branch frame count differs')
    for name in ('road.xodr',_generation_source_key(certificate),'capture/manifest.json','capture/evidence.jsonl','capture/native_map_facts.json','carla_recorder.log'):
        if name not in originals:raise ValueError('Missing analytical source input: '+name)
    checked('source-inspection.json',certificate['source_inspection'])
    checked('route-module.py',packet['route_module'])
    local_sources=[x for x in certificate.get('official_sources',[])if 'path'in x]
    if len(local_sources)<3:raise ValueError('Incomplete collision-generator source contract')
    source_contracts = {Path(reference['path']).name: checked(Path(reference['path']).name, reference) for reference in local_sources}
    ceiling=_source_generated_opaque_ceiling(certificate,originals,source_contracts)
    if (digest(originals['road.xodr'])!=packet['xodr']['sha256'] or packet['xodr']['sha256']!=certificate['xodr_sha256']
            or certificate['retained_frame_table_sha256']!=frames_digest
            or table['original_source']['sha256']!=certificate['original_sources']['capture/evidence.jsonl']['sha256']):
        raise ValueError('Analytical visibility map/original frame identity differs')
    xml=ET.parse(originals['road.xodr']).getroot()
    ground_plane=(_source_reference_ground_plane(xml,certificate['reference_ground_plane'],
                   certificate['generation_parameters']['wall_height'])[0]
                  if 'reference_ground_plane' in certificate else None)
    if ground_plane is None:
        from .road_visibility_geometry import source_road_interior
        ground_plane=source_road_interior(xml,source_contracts,ceiling,certificate['generation_parameters'])
    _source_nonrendered_object_declarations(xml, source_contracts)
    if (xml.findall('./road/signals/signalReference')
            or xml.findall('./road/signals/signal') and certificate.get('opaque_static_enclosures') is None):
        raise ValueError('Analytical zero-ceiling source has additional object declarations')
    # Constant vertical profiles and banking were source-qualified with the ceiling.
    for lane in xml.findall('./road/lanes/laneSection/*/lane'):
        if lane.get('type') == 'shoulder':
            lane_source=source_contracts.get('Lane.cpp')
            if lane_source is None or digest(lane_source)!='53adedca967bf6e617bc47b861307a37e831baa604f0fae165577deec1704289':
                raise ValueError('Unqualified native shoulder reference geometry')
        if lane.get('type') not in ('driving', 'none', 'sidewalk', 'shoulder'):
            raise ValueError('Analytical source has unsupported lane geometry')
        # The pinned native Lane.cpp uses its binary32 sidewalk offset and
        # explicitly does not consume sidewalk Lane Height Records. Other
        # nonzero lane heights remain outside this source-model admission.
        if (lane.get('type') != 'sidewalk'
                and any(float(height.get(key, '0')) != 0.
                        for height in lane.findall('height') for key in ('inner', 'outer'))):
            raise ValueError('Analytical source has unsupported raised lane geometry')
    from .body_capture import source_events as original_body_events
    source_events = original_body_events(certificate, originals)
    retained={r['frame']:r for r in table['frames']}
    frames=packet['frames']
    static_enclosures,static_actors=_source_generated_speed_sign_enclosures(certificate,originals,source_events,xml,checked)
    vehicle_enclosures,native_queries=_source_vehicle_enclosures(certificate,originals,source_events,packet,checked,inventory,static_actors)
    enclosures=None if static_enclosures is None and vehicle_enclosures is None else {frame:(vehicle_enclosures or {}).get(frame,[])+(static_enclosures or {}).get(frame,[]) for frame in source_events}
    if static_enclosures is not None:
        registry=certificate['native_actor_registry'];opaque={int(k) for k,v in registry.items() if (v if isinstance(v,str)else v['name'])!='spectator' and not(v if isinstance(v,str)else v['name']).startswith('sensor.')}
        for frame,event in source_events.items():
            if opaque!={event['actor_id']}|{box['actor_id'] for box in enclosures[frame]}:
                raise ValueError('Unaccounted original opaque actor enclosure')
    road_surface = _source_finite_opaque_road_surface(certificate, xml, checked)
    if road_surface is not None:
        enclosures = {frame: (enclosures or {}).get(frame, []) +
            [{'_source_reference_components': road_surface,
              'source_geometry_kind': 'finite_opaque_driving_surface'}] for frame in source_events}
    selected_ids = {f['original_frame'] for f in frames}
    if (len(retained)!=len(table['frames']) or len(frames)!=packet['frame_count'] or len(selected_ids)!=len(frames)
            or set(retained)!=set(source_events) or not selected_ids<=set(retained)):
        raise ValueError('Analytical visibility frame inventory differs')
    source_scope = packet.get('frame_scope')
    if selected_ids!=set(retained):
        if (enclosures is None or source_scope not in ('verified_clear_subset', 'verified_source_subset')
                or packet.get('recording_frame_count')!=len(retained)):
            raise ValueError('Forged or unspecified partial clear frame scope')
    elif vehicle_enclosures is not None and (source_scope not in ('verified_clear_subset', 'verified_source_subset')
            or packet.get('recording_frame_count')!=len(retained)):
        raise ValueError('Forged or unspecified partial clear frame scope')
    unknown = {f['original_frame'] for f in frames if any(lane.get('state') == 'unknown' for lane in f['required_lane_results'])}
    if set(branch_frames) != unknown:
        raise ValueError('Native branch supplement frame coverage differs')
    settings=packet['settings'];eye,probe,maximum,step,tolerance=(settings[k]for k in ('observer_height_m','probe_m','search_limit_m','step_m','tolerance_m'))
    if any(type(v)not in(int,float)or not math.isfinite(v)or v<=0 for v in (eye,probe,maximum,step,tolerance)):
        raise ValueError('Invalid analytical visibility sampling convention')
    distances=sorted(set([0.]+[min(i*step,maximum)for i in range(1,math.ceil(maximum/step)+1)]+[probe]))
    roads={int(r.get('id')):r for r in xml.findall('road')};results={};last_time=None
    for frame in frames:
        ident=frame['original_frame'];raw=source_events[ident];original=retained[ident];actor=frame['actor_id'];time=frame['recording_time_s'];vertices=raw['ego']['body_vertices_m'];samples=frame['actual_body_samples_m']
        if (actor!=raw['actor_id'] or actor!=original['actor_id'] or abs(time-raw['recording_time_s'])>1e-6
                or abs(time-original['time_s'])>1e-6 or last_time is not None and time<=last_time
                or original['body_vertices_m']!=vertices or frame['ego_position_m']!=raw['ego']['position_m']
                or original['position_m']!=raw['ego']['position_m'] or len(samples)!=9
                or any(not _finite_vector(v)for v in samples)or samples[1:]!=vertices):
            raise ValueError('Analytical visibility actor/frame/body join differs')
        centre=[sum(p[i]for p in vertices)/len(vertices)for i in range(3)]
        if math.dist(samples[0],centre)>1e-6:raise ValueError('Analytical body reference centre differs')
        last_time=time
        registry={key: value if isinstance(value,str) else value['name'] for key,value in certificate['native_actor_registry'].items()}
        if str(actor)not in registry or not registry[str(actor)].startswith(('vehicle.','walker.')) or (enclosures is None and any(k!=str(actor)and not(v=='spectator'or v.startswith('sensor.'))for k,v in registry.items())):
            raise ValueError('Analytical source has another potentially opaque actor')
        road=roads.get(frame['native_road_id']);station=frame['native_station_m']
        if road is None or type(station)not in(int,float)or not math.isfinite(station)or not 0<=station<=float(road.get('length')):
            raise ValueError('Analytical current road location unavailable')
        section=max((s for s in road.findall('lanes/laneSection')if float(s.get('s'))<=station),key=lambda s:float(s.get('s')))
        required=sorted(int(l.get('id'))for l in section.findall('left/lane')+section.findall('right/lane')if l.get('type')=='driving')
        lanes=frame['required_lane_results']
        if not required or len(lanes)!=len(required)or sorted(r['lane_id']for r in lanes)!=required:
            raise ValueError('Analytical approach inventory incomplete')
        branch_lanes = {}
        if ident in branch_frames:
            supplied = branch_frames[ident]['lane_results']
            branch_lanes = {lane['lane']: lane for lane in supplied}
            expected_branches = sorted(lane['lane_id'] for lane in lanes if lane.get('state') == 'unknown')
            if len(supplied) != len(branch_lanes) or sorted(branch_lanes) != expected_branches:
                raise ValueError('Native branch lane inventory differs')
        approaches=[]
        for lane in lanes:
            route=lane['route'];observations=lane['sample_certificates']
            if lane['lane_id'] in branch_lanes:
                if (lane['road_id'] != frame['native_road_id'] or lane.get('state') != 'unknown'
                        or route.get('unknown_reason') != 'ambiguous modeled predecessor'):
                    raise ValueError('Native supplement does not resolve this source limitation')
                paths = _native_branch_paths(branch_lanes[lane['lane_id']], native_nodes)
                alternatives, proofs = [], []
                for path in paths:
                    provenance = dict(path['provenance'])
                    provenance['connections'] = [dict(item, source='native predecessor on enumerated route')
                                                 for item in provenance.get('connections', [])]
                    provenance['selection_policy'] = 'minimum over all actual native paths'
                    samples_on_path = []
                    for probe_sample in path['probes']:
                        observer = probe_sample.get('observer_m')
                        if not _finite_vector(observer):
                            raise ValueError('Incomplete native branch observer')
                        indices = [i for i, point in enumerate(samples)
                                   if _analytic_segment_ground_clearance(observer,point,ceiling,ground_plane)>0 and not any(_segment_intersects_enclosure(observer, point, box) for box in (enclosures or {}).get(ident, []))]
                        samples_on_path.append({'distance_m': probe_sample['distance_m'],
                                                'observer_m': observer, 'clear_sample_indices': indices,
                                                'minimum_proved_vertical_clearance_m': probe_sample.get('positive_vertical_clearance_m')})
                    native = _enclosure_native_positions(native_queries, ident, lane['lane_id'], path['branch_choices'])
                    state = path.get('state')
                    if state == 'first_sampled_occlusion':
                        path_lane = dict(path, lane_id=lane['lane_id'], route=provenance,
                                         sample_certificates=samples_on_path)
                        finite = _analytic_first_loss_lane(path_lane, distances, samples,
                            raw, ceiling, eye, maximum, probe, tolerance, packet['xodr']['sha256'],
                            (enclosures or {}).get(ident, []), native, ground_plane)
                        horizon = finite['any_body_sight_horizon']
                        probe_clear = finite.get('any_sample_clear_at_probe')
                    elif state == 'censored_clear_prefix':
                        horizon = _analytic_clear_prefix(dict(path, provenance=provenance),
                            samples_on_path, distances, samples, ceiling, eye, maximum,
                            probe, tolerance, packet['xodr']['sha256'],
                            (enclosures or {}).get(ident, []), native, ground_plane)
                        probe_row = next(row for row in samples_on_path if row['distance_m'] == probe)
                        probe_clear = (True if probe_row['clear_sample_indices'] else False
                            if _analytic_row_blocked(probe_row, samples, raw, (enclosures or {}).get(ident, [])) else None)
                    else:
                        if state != 'at_least' and lane.get('all_paths_complete_and_clear') is not True:
                            raise ValueError('Unqualified native path horizon')
                        _analytic_route_samples(provenance, samples_on_path, distances, samples, ceiling, eye,
                                                maximum, packet['xodr']['sha256'], (enclosures or {}).get(ident, []),
                                                native, ground_plane)
                        horizon = {'bound': 'at_least', 'distance_m': maximum}
                        probe_clear = True
                    alternatives.append(provenance)
                    proofs.append({'branch_choices': path['branch_choices'], 'observer_route': provenance,
                                   'analytic_sample_certificates': samples_on_path,
                                   'any_body_sight_horizon': horizon,
                                   'search_tail_unresolved': state == 'censored_clear_prefix'})
                    if probe_clear is not None:
                        proofs[-1]['any_sample_clear_at_probe'] = probe_clear
                    else:
                        proofs[-1]['probe_unknown_reason'] = 'No qualified clear or opaque-hit proof at later probe'
                approach = {'lane_id': lane['lane_id'], 'observer_routes': alternatives,
                                   'any_body_sight_horizon': _minimum_path_horizon(proofs, tolerance, False),
                                   'native_branch_paths': proofs}
                probe_values = [path.get('any_sample_clear_at_probe') for path in proofs]
                if all(value is True for value in probe_values):
                    approach['any_sample_clear_at_probe'] = True
                elif any(value is False for value in probe_values):
                    approach['any_sample_clear_at_probe'] = False
                else:
                    approach['probe_unknown_reason'] = 'A native path has an unresolved later probe'
                approaches.append(approach)
                continue
            if lane.get('state') == 'first_sampled_occlusion':
                if (source_scope != 'verified_source_subset'
                        or lane['road_id'] != frame['native_road_id']
                        or lane.get('search_limit_m') != maximum):
                    raise ValueError('Unqualified analytical finite-horizon scope')
                approaches.append(_analytic_first_loss_lane(lane, distances, samples,
                    raw, ceiling, eye, maximum, probe, tolerance, packet['xodr']['sha256'],
                    (enclosures or {}).get(ident, []),
                    _enclosure_native_positions(native_queries, ident, lane['lane_id'], []),
                    ground_plane))
                continue
            if (lane['road_id']!=frame['native_road_id']or lane.get('state')!='at_least'or lane.get('distance_m')!=maximum
                    or lane.get('search_limit_m')!=maximum):
                raise ValueError('Analytical route/search coverage incomplete')
            _analytic_route_samples(route, observations, distances, samples, ceiling, eye,
                                    maximum, packet['xodr']['sha256'], (enclosures or {}).get(ident, []),
                                    _enclosure_native_positions(native_queries, ident, lane['lane_id'], []),ground_plane)
            approaches.append({'lane_id':lane['lane_id'],'observer_route':route,'any_sample_clear_at_probe':True,
                'any_body_sight_horizon':{'bound':'at_least','distance_m':maximum},'analytic_sample_certificates':observations})
        # A partial path may only contribute a dominated lower bound to the
        # complete place measurement. Every native alternative remains exposed.
        minimum_horizon = _minimum_path_horizon([path for approach in approaches
            for path in approach.get('native_branch_paths', [approach])], tolerance)
        visibility={'method':ANALYTIC_METHOD,'distance_convention':TERMINAL_CONVENTION,'visibility_criterion':'any_of_nine_body_samples',
            'actual_actor_origin_m':frame['ego_position_m'],'ego_projection':{'road_id':frame['native_road_id'],'lane_id':frame['native_lane_id'],'s_m':station},
            'ego_body_samples_m':samples,'eye_height_m':eye,'probe_distance_m':probe,'maximum_search_distance_m':maximum,
            'maximum_observer_route_distance_m':max(probe,maximum),'scan_step_m':step,'horizon_tolerance_m':tolerance,
            'required_lane_ids':required,'approaches':approaches,'analytic_source':{'schema':'verified_source_bound_analytic_reference_v1',
                'source_inputs_verified':True,'no_cast_ray_executed':True,'packet_sha256':packet_digest,
                'certificate_sha256':certificate_digest,'retained_frames_sha256':frames_digest,
                'generated_road_geometry_upper_z_m':ceiling,'source_model':certificate['source_model']}}
        if 'reference_ground_plane' in certificate:
            visibility['analytic_source']['reference_ground_plane']=dict(certificate['reference_ground_plane'])
        elif ground_plane is not None:
            visibility['analytic_source']['finite_road_interior']=ground_plane.provenance()
        visibility['analytic_source']['minimum_path_horizon'] = minimum_horizon
        if road_surface is not None:
            visibility['analytic_source']['finite_opaque_road_surface_sha256'] = certificate['finite_opaque_road_surface']['sha256']
        if static_enclosures is not None:
            visibility['analytic_source']['opaque_static_enclosures_sha256']=certificate['opaque_static_enclosures']['sha256']
            visibility['analytic_source']['static_pose_source']='derived_static'
        if vehicle_enclosures is not None:
            visibility['analytic_source']['opaque_vehicle_enclosures_sha256'] = certificate['opaque_vehicle_enclosures']['sha256']
            visibility['analytic_source']['frame_scope'] = source_scope
            visibility['analytic_source']['recording_frame_count'] = len(retained)
        if selected_ids!=set(retained):
            visibility['analytic_source']['frame_scope'] = source_scope
            visibility['analytic_source']['recording_frame_count'] = len(retained)
        if supplement is not None:
            visibility['analytic_source']['supplement_sha256'] = supplement_digest
            visibility['analytic_source']['native_alternative_inventory_sha256'] = supplement['native_alternative_inventory']['sha256']
            visibility['analytic_source']['native_branch_proof_sha256'] = supplement['branch_proof']['sha256']
        stamp=round(time*1000)
        if stamp in results:raise ValueError('Analytical visibility timestamps collide')
        results[stamp]={'subject':actor,'original_frame':ident,'recording_time_s':time,'actor_origin_m':frame['ego_position_m'],
            'body_vertices_m':vertices,'visibility':_VerifiedAnalyticVisibility(visibility).seal()}
    return results


def retained_analytic_visibility(evidence):
    """Read optional hash-bound derived inputs without modifying original capture."""
    import json,hashlib
    declaration=evidence.path('derived_reference_visibility.json')
    if declaration is None:return {}
    document=json.loads(declaration.read_text())
    if document.get('schema')!='derived_reference_visibility_inputs_v1':raise ValueError('Unknown derived visibility declaration')
    def locate(name,reference):
        relative=document.get('source_bindings',{}).get(reference['path'],name)
        path=evidence.path(relative)
        if path is None:raise ValueError('Unbound derived visibility source: '+relative)
        digest=hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=reference['sha256']:raise ValueError('Derived visibility source hash mismatch: '+relative)
        return path
    paths={name:locate(name,document[name])for name in('packet','certificate','frames')}
    supplement = locate('supplement', document['supplement']) if 'supplement' in document else None
    return load_analytic_reference_visibility(paths['packet'],paths['certificate'],paths['frames'],source_resolver=locate,supplement_path=supplement)


def _source_body_oriented_enclosure(vertices):
    """Enclose all original API corners in an orthonormal source-derived basis.

    This refines the existing body-box estimate, not the rendered vehicle mesh.
    Never accept producer-supplied axes in place of the original eight corners.
    """
    if len(vertices) != 8 or any(not _finite_vector(p) for p in vertices):
        raise ValueError('Invalid original oriented body corners')
    def dot(a, b):
        return math.fsum(x*y for x, y in zip(a, b))
    def normalize(a):
        length = math.sqrt(dot(a, a))
        if not math.isfinite(length) or length <= 1e-10:
            raise ValueError('Degenerate original body basis')
        return [x/length for x in a]
    center = [math.fsum(p[j] for p in vertices)/8 for j in range(3)]
    x = normalize([vertices[4][j]-vertices[0][j] for j in range(3)])
    raw_y = [vertices[2][j]-vertices[0][j] for j in range(3)]
    xy = dot(raw_y, x)
    y = normalize([raw_y[j]-xy*x[j] for j in range(3)])
    z = normalize([x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0]])
    axes = [x, y, z]
    if max(abs(dot(a, b)-(1. if i == j else 0.))
           for i, a in enumerate(axes) for j, b in enumerate(axes)) > 1e-12:
        raise ValueError('Nonorthonormal original body basis')
    pad = 64*2**-23*max(1., *(abs(v) for p in vertices for v in p))
    coordinates = [[dot([p[j]-center[j] for j in range(3)], axis)
                    for axis in axes] for p in vertices]
    low = [min(p[j] for p in coordinates)-pad for j in range(3)]
    high = [max(p[j] for p in coordinates)+pad for j in range(3)]
    if any(high[j]-low[j] <= 2*pad for j in range(3)):
        raise ValueError('Degenerate original body extent')
    return {'origin_m': center, 'axes': axes, 'low_m': low, 'high_m': high}


def _segment_intersects_oriented_body(a, b, box):
    origin, axes = box['origin_m'], box['axes']
    aa, bb = [[math.fsum((p[j]-origin[j])*axis[j] for j in range(3))
               for axis in axes] for p in (a, b)]
    guard = 64*2**-52*max(1., *(abs(x) for p in (a, b, origin) for x in p))
    expanded = {'low_m': [x-guard for x in box['low_m']],
                'high_m': [x+guard for x in box['high_m']]}
    return _segment_intersects_enclosure(aa, bb, expanded)


def _segment_intersects_enclosure(a, b, box):
    reference = box.get('_source_reference_components')
    if reference is not None:return reference.intersects(a, b)
    low, high = 0., 1.
    for axis in range(3):
        delta = b[axis] - a[axis]
        if delta == 0:
            if a[axis] < box['low_m'][axis] or a[axis] > box['high_m'][axis]:return False
        else:
            enter = (box['low_m'][axis] - a[axis]) / delta
            leave = (box['high_m'][axis] - a[axis]) / delta
            low, high = max(low, min(enter, leave)), min(high, max(enter, leave))
            if low > high:return False
    oriented = box.get('_source_oriented_body')
    return oriented is None or _segment_intersects_oriented_body(a, b, oriented)


def _source_static_reference_enclosures(certificate, originals, events, checked, data):
    """Complete decoded Stop assembly at independently captured Native poses."""
    import json, re
    if (data.get('schema') != 'source_bound_static_render_reference_enclosures_v1'
            or data.get('recording_id') != certificate['recording_id']):
        raise ValueError('Static reference recording identity differs')
    census = re.findall(r' Create (\d+): (\S+) ', originals['capture/recorder_info.txt'].read_text())
    registry = dict(census)
    declared = {str(k): v if isinstance(v, str) else v['name']
                for k, v in certificate['native_actor_registry'].items()}
    if len(census) != len(registry) or registry != declared:
        raise ValueError('Static reference Native census differs')
    rows = data.get('actors', [])
    actors = {row.get('actor_id') for row in rows}
    expected = {int(k) for k, name in registry.items() if name == 'traffic.stop'}
    if not actors or len(actors) != len(rows) or actors != expected:
        raise ValueError('Incomplete static reference actor inventory')
    geometries = {}
    required = ('road.xodr', 'runner.py', 'capture/manifest.json', 'capture/evidence.jsonl',
                'capture/recorder_info.txt', 'channels/native_actor_inventory.jsonl')
    for row in rows:
        actor = row['actor_id']
        q = json.loads(checked('static-reference-qualification-'+str(actor), row['qualification']).read_text())
        if (row.get('blueprint') != 'traffic.stop' or registry.get(str(actor)) != 'traffic.stop'
                or q.get('schema') != 'source_qualified_static_render_reference_v1'
                or q.get('recording_id') != certificate['recording_id']
                or q.get('blueprint') != row['blueprint']
                or q.get('geometry_sha256') != row['geometry']['sha256']
                or q.get('complete_applicable_component_coverage') is not True
                or q.get('method_is_declared_geometry_reference_estimate') is not True
                or q.get('pose_source') != 'native_static_inventory_and_original_device_position_v1'):
            raise ValueError('Incomplete static reference component qualification')
        for name in required:
            if (name not in originals or q.get('original_source_hashes', {}).get(name)
                    != certificate['original_sources'][name]['sha256']):
                raise ValueError('Static reference original source differs')
        references = q.get('source_references', {})
        if not all(name in references for name in ('asset_component_bindings', 'render_export',
                                                  'configuration_coverage', 'root_transform_contract')):
            raise ValueError('Missing static reference coverage contract')
        _check_reference_dependencies(references, checked, {r['sha256'] for r in certificate['original_sources'].values()})
        geometry = json.loads(checked('static-reference-geometry-'+str(actor), row['geometry']).read_text())
        vertices = geometry.get('vertices_m', [])
        if (geometry.get('schema') != 'source_bound_static_render_vertices_v1' or not vertices
                or any(not _finite_vector(point) for point in vertices)):
            raise ValueError('Invalid complete static reference vertices')
        radius = max(math.hypot(point[0], point[1]) for point in vertices)
        low, high = min(p[2] for p in vertices), max(p[2] for p in vertices)
        if radius <= 0 or low >= high:raise ValueError('Empty static reference geometry')
        geometries[actor] = (radius, low, high)
    pattern = (r'Transform\(Location\(x=([^,]+), y=([^,]+), z=([^\)]+)\), '
               r'Rotation\(pitch=([^,]+), yaw=([^,]+), roll=([^\)]+)\)\)')
    result = {}
    with originals['channels/native_actor_inventory.jsonl'].open() as source:
        for line in source:
            outer = json.loads(line)
            native = outer['value']
            frame = native['frame']
            event = events.get(frame)
            full = native.get('complete_actor_inventory', [])
            roles = {str(item['id']): item['type_id'] for item in full}
            traffic = native.get('traffic_actor_inventory', [])
            by_actor = {item['id']: item for item in traffic}
            devices = {item['actor_id']: item for item in event['devices']} if event else {}
            if (frame in result or event is None or len(roles) != len(full) or roles != registry
                    or native.get('unclassified_actor_types') or len(by_actor) != len(traffic)
                    or set(by_actor) != actors or len(devices) != len(event['devices'])
                    or set(devices) != actors or outer['time_s'] != event['recording_time_s']):
                raise ValueError('Static reference original frame or scene coverage differs')
            bounds = []
            for actor, (radius, zlow, zhigh) in geometries.items():
                item, device = by_actor[actor], devices[actor]
                match = re.fullmatch(pattern, item.get('native_transform', ''))
                pose = [float(value) for value in match.groups()] if match else []
                origin = device.get('position_m')
                if (item.get('type_id') != 'traffic.stop' or device.get('blueprint') != 'traffic.stop'
                        or len(pose) != 6 or any(not math.isfinite(x) for x in pose)
                        or pose[3] != 0 or pose[5] != 0 or not _finite_vector(origin)
                        or max(abs(origin[j]-pose[j]) for j in range(3)) > 1e-5):
                    raise ValueError('Static reference original pose or component frame differs')
                pad = 64*2**-23*max(1., radius, abs(zlow), abs(zhigh), *(abs(x) for x in origin))
                bounds.append({'actor_id': actor,
                    'low_m': [origin[0]-radius-pad, origin[1]-radius-pad, origin[2]+zlow-pad],
                    'high_m': [origin[0]+radius+pad, origin[1]+radius+pad, origin[2]+zhigh+pad]})
            result[frame] = bounds
    if set(result) != set(events):raise ValueError('Incomplete static reference Native frame inventory')
    return result, actors


def _source_generated_traffic_light_enclosures(certificate, originals, events, checked, data):
    """Complete source components, bounded separately at recorded actor roots."""
    import json, re
    import numpy as np
    if (data.get('schema') != 'source_bound_generated_traffic_light_reference_enclosures_v1'
            or data.get('recording_id') != certificate['recording_id']):
        raise ValueError('Traffic-light reference recording identity differs')
    q = json.loads(checked('traffic-light-reference-qualification', data['qualification']).read_text())
    if (q.get('schema') != 'source_qualified_generated_traffic_light_component_reference_v1'
            or q.get('recording_id') != certificate['recording_id']
            or q.get('method_is_declared_geometry_reference_estimate') is not True
            or q.get('complete_applicable_mesh_component_scope', {}).get('runtime_geometry_changes_present') is not False
            or q.get('complete_applicable_mesh_component_scope', {}).get('original_runner_mutates_only_signal_state_freeze') is not True):
        raise ValueError('Incomplete generated traffic-light assembly qualification')
    for name in ('road.xodr', 'runner.py', 'actual_scene_identity.json', 'capture/manifest.json',
                 'capture/evidence.jsonl', 'carla_recorder.log', 'capture/recorder_info.txt'):
        if (name not in originals or q.get('original_sources', {}).get(name, {}).get('sha256')
                != certificate['original_sources'][name]['sha256']):
            raise ValueError('Traffic-light original source identity differs')
    required = ('raw_blueprint_assets', 'blueprint_decode', 'factory_source', 'native_parent_source',
                'component_geometry', 'model_vertices', 'all_source_asset_export_refs', 'own_root_head_body_census_join')
    if any(name not in q for name in required):
        raise ValueError('Missing generated traffic-light source contract')
    _check_reference_dependencies({name: q[name] for name in required}, checked,
        {r['sha256'] for r in certificate['original_sources'].values()})
    geometry = json.loads(checked('traffic-light-component-geometry', q['component_geometry']).read_text())
    if geometry.get('model') != q['model_vertices']:
        raise ValueError('Traffic-light component buffer binding differs')
    components = geometry.get('components', [])
    keys = [item.get('points_key') for item in components]
    if not keys or len(keys) != len(set(keys)):
        raise ValueError('Incomplete traffic-light component enumeration')
    envelopes = []
    with np.load(checked('traffic-light-reference-vertices', q['model_vertices']), allow_pickle=False) as model:
        if set(model.files) != set(keys):raise ValueError('Traffic-light component inventory differs')
        for key in keys:
            vertices = model[key]
            if vertices.ndim != 2 or vertices.shape[1:] != (3,) or not len(vertices) or not np.isfinite(vertices).all():
                raise ValueError('Invalid traffic-light component vertices')
            # Separate high arms/heads from low poles; an all-yaw radial bound
            # on each component does not invent a solid volume below the arm.
            envelopes.append((float(np.hypot(vertices[:, 0], vertices[:, 1]).max()),
                              float(vertices[:, 2].min()), float(vertices[:, 2].max())))
    roots = json.loads(checked('traffic-light-own-native-roots', q['own_root_head_body_census_join']).read_text())
    for field, name in (('raw_recorder', 'carla_recorder.log'), ('original_capture', 'capture/evidence.jsonl'),
                        ('original_manifest', 'capture/manifest.json')):
        if roots.get(field, {}).get('sha256') != certificate['original_sources'][name]['sha256']:
            raise ValueError('Traffic-light Native root derivation differs')
    checked('traffic-light-native-packet-source', roots['packet_source'])
    if (roots.get('original_frames') != len(events) or roots.get('no_actor_deletions') is not True
            or roots.get('packet_source', {}).get('sha256') != 'edae97685d4a905d52c857c32e85075bdc4fe5075add3b8af30a9f2ad3f66e87'):
        raise ValueError('Incomplete traffic-light Native root interval contract')
    census = re.findall(r' Create (\d+): (\S+) ', originals['capture/recorder_info.txt'].read_text())
    registry = dict(census)
    declared = {str(k): value if isinstance(value, str) else value['name']
                for k, value in certificate['native_actor_registry'].items()}
    adds = roots.get('complete_initial_adds', [])
    added = {str(item['actor_id']): item['blueprint'] for item in adds}
    if len(census) != len(registry) or registry != declared or len(adds) != len(added) or added != registry:
        raise ValueError('Traffic-light complete original Native census differs')
    records = roots.get('traffic_light_roots', [])
    actors = {row.get('actor_id') for row in records}
    expected = {int(key) for key, name in registry.items() if name == 'traffic.traffic_light'}
    if not actors or len(actors) != len(records) or actors != expected:
        raise ValueError('Incomplete generated traffic-light root inventory')
    origins = {}
    for row in records:
        origin, euler = row.get('position_native_m'), row.get('euler_native_deg')
        if (row.get('blueprint') != 'traffic.traffic_light' or not _finite_vector(origin)
                or not _finite_vector(euler) or euler[0] != 0 or euler[1] != 0):
            raise ValueError('Unsupported generated traffic-light reference root')
        origins[row['actor_id']] = origin
    result = {}
    for frame, event in events.items():
        devices = {row['actor_id']: row for row in event['devices']}
        if len(devices) != len(event['devices']) or set(devices) != actors:
            raise ValueError('Incomplete original traffic-light API inventory')
        bounds = []
        for actor, origin in origins.items():
            observed = devices[actor]
            if (observed.get('blueprint') != 'traffic.traffic_light'
                    or not _finite_vector(observed.get('position_m'))
                    or math.dist(observed['position_m'], origin) > 1e-5):
                raise ValueError('Original traffic-light root pose differs')
            for radius, low, high in envelopes:
                pad = 64*2**-23*max(1., radius, abs(low), abs(high), *(abs(x) for x in origin))
                bounds.append({'actor_id': actor,
                    'low_m': [origin[0]-radius-pad, origin[1]-radius-pad, origin[2]+low-pad],
                    'high_m': [origin[0]+radius+pad, origin[1]+radius+pad, origin[2]+high+pad]})
        result[frame] = bounds
    return result, actors


def _source_generated_speed_sign_enclosures(certificate, originals, events, xml, checked):
    """Consume complete source-qualified component bounds, never trigger boxes.

    Asset decoding/qualification belongs to the producer, not this exporter.
    All source identities, declarations, poses and bounds remain hash-bound.
    """
    import json,re
    reference=certificate.get('opaque_static_enclosures')
    if reference is None:return None,set()
    data=json.loads(checked('opaque-static-enclosures.json',reference).read_text())
    if data.get('schema') == 'source_bound_static_enclosure_collection_v1':
        if data.get('recording_id') != certificate['recording_id'] or not data.get('sources'):
            raise ValueError('Invalid static enclosure collection identity/scope')
        merged, actors = {frame: [] for frame in events}, set()
        for item in data['sources']:
            child = json.loads(checked('static-enclosure-collection-item', item).read_text())
            if child.get('schema') == 'source_bound_static_enclosure_collection_v1':
                raise ValueError('Nested static enclosure collections are unsupported')
            bounds, ids = _source_generated_speed_sign_enclosures(
                dict(certificate, opaque_static_enclosures=item), originals, events, xml, checked)
            if not ids or actors & ids or set(bounds) != set(events):
                raise ValueError('Overlapping or incomplete static enclosure collection')
            actors.update(ids)
            for frame in events: merged[frame].extend(bounds[frame])
        return merged, actors
    if data.get('schema')=='source_bound_generated_traffic_light_reference_enclosures_v1':
        return _source_generated_traffic_light_enclosures(certificate,originals,events,checked,data)
    if data.get('schema')=='source_bound_static_render_reference_enclosures_v1':
        return _source_static_reference_enclosures(certificate,originals,events,checked,data)
    if data.get('schema')=='source_bound_named_stock_prop_API_enclosures_v1':
        return _source_named_stock_prop_api_enclosures(certificate,originals,events,checked,data)
    if data.get('schema')=='source_bound_static_mesh_render_API_enclosures_v1':
        return _source_static_mesh_api_enclosures(certificate,originals,events,checked,data)
    required=('road.xodr','runner.py','capture/manifest.json','capture/evidence.jsonl','capture/recorder_info.txt')
    if (data.get('schema')!='source_bound_generated_speed_sign_enclosures_v1'
            or data.get('recording_id')!=certificate['recording_id']
            or data.get('complete_opaque_components')is not True
            or any(name not in originals or data.get('source_hashes',{}).get(name)!=certificate['original_sources'][name]['sha256'] for name in required)):
        raise ValueError('Unqualified generated speed-sign enclosure source')
    manifest=json.loads(originals['capture/manifest.json'].read_text())
    if manifest.get('acquisition')!='original_live_run' or manifest.get('observation_contract_version')not in(2,3):
        raise ValueError('Unsupported original static geometry acquisition contract')
    proofs=data.get('source_proofs',{})
    if not all(name in proofs for name in ('asset_identity','component_geometry','scene_geometry')):
        raise ValueError('Incomplete generated speed-sign source qualification')
    for name,proof in proofs.items():checked('static-source-'+name,proof)
    registry={}
    for line in originals['capture/recorder_info.txt'].read_text().splitlines():
        match=re.match(r' Create (\d+): (\S+) ',line)
        if match:
            if match[1]in registry:raise ValueError('Duplicate original static actor identity')
            registry[match[1]]=match[2]
    declared={str(k):v if isinstance(v,str)else v['name'] for k,v in certificate['native_actor_registry'].items()}
    if registry!=declared:raise ValueError('Static actor census differs from original source')
    signals={(int(road.get('id')),signal.get('id')):signal for road in xml.findall('road') for signal in road.findall('./signals/signal')}
    if len(signals)!=len(xml.findall('./road/signals/signal')):raise ValueError('Duplicate source XML signal identity')
    rows=data.get('actors',[]);actors=set();covered=set();bounds=[]
    for row in rows:
        actor=row.get('actor_id');key=(row.get('road_id'),row.get('signal_id'));signal=signals.get(key)
        if (type(actor)is not int or type(row.get('road_id'))is not int or not isinstance(row.get('signal_id'),str) or not row['signal_id']
                or actor in actors or key in covered or signal is None
                or row.get('signal_attributes')!=dict(signal.attrib) or signal.get('type')!='274' or not signal.get('subtype','').isdigit()
                or row.get('blueprint')!='traffic.speed_limit.'+signal.get('subtype','')
                or registry.get(str(actor))!=row['blueprint'] or row.get('pose_source')!='derived_static'):
            raise ValueError('Unqualified or unmatched generated speed-sign actor')
        qualification=json.loads(checked('static-qualification-'+str(actor),row['qualification']).read_text())
        if (qualification.get('schema')!='source_qualified_generated_speed_sign_geometry_v1'
                or qualification.get('recording_id')!=certificate['recording_id'] or qualification.get('actor_id')!=actor
                or qualification.get('blueprint')!=row['blueprint'] or qualification.get('source_hashes')!=data['source_hashes']
                or qualification.get('setup_sha256')!=row['original_setup']['sha256']
                or qualification.get('enclosure_sha256')!=row['enclosure']['sha256']
                or qualification.get('asset_sha256')!=sorted(a['sha256'] for a in row.get('asset_sources',[]))
                or qualification.get('complete_opaque_components')is not True or qualification.get('immutable_static_pose')is not True):
            raise ValueError('Unqualified static speed-sign geometry or pose contract')
        setup=json.loads(checked('static-setup-'+str(actor),row['original_setup']).read_text())
        landmark=setup.get('landmark',{});pose=setup.get('transform',{});position=pose.get('position_m',{});rotation=pose.get('rotation_degrees',{})
        origin=[position.get(k) for k in ('x','y','z')]
        orientation={'Positive':'+','Negative':'-','Both':'none'}.get(landmark.get('orientation'))
        if (setup.get('actor_id')!=actor or setup.get('blueprint')!=row['blueprint']
                or landmark.get('id')!=key[1] or landmark.get('road_id')!=key[0]
                or landmark.get('type')!=signal.get('type') or landmark.get('sub_type')!=signal.get('subtype')
                or orientation!=signal.get('orientation') or landmark.get('unit')!=signal.get('unit')
                or type(landmark.get('value'))not in(int,float) or not math.isfinite(landmark['value'])
                or not math.isfinite(float(signal.get('value','nan'))) or abs(landmark['value']-float(signal.get('value','nan')))>1e-6
                or not _finite_vector(origin)
                or any(type(rotation.get(k))not in(int,float) or not math.isfinite(rotation[k]) for k in ('pitch','roll','yaw'))
                or any(type(landmark.get(k))not in(int,float) or not math.isfinite(landmark[k]) or not math.isfinite(float(signal.get(xmlkey,'nan'))) or abs(landmark[k]-float(signal.get(xmlkey,'nan')))>1e-6 for k,xmlkey in (('s_m','s'),('t_m','t')))):
            raise ValueError('Generated speed-sign source signal or pose differs')
        assets=row.get('asset_sources',[])
        if not assets:raise ValueError('Missing qualified speed-sign asset sources')
        for index,asset in enumerate(assets):checked('static-asset-'+str(actor)+'-'+str(index),asset)
        geometry=json.loads(checked('static-geometry-'+str(actor),row['enclosure']).read_text())
        low,high=geometry.get('low_m'),geometry.get('high_m');radius=geometry.get('radius_m')
        if (geometry.get('actor_id')!=actor or geometry.get('blueprint')!=row['blueprint']
                or not _finite_vector(low) or not _finite_vector(high) or type(radius)not in(int,float) or not math.isfinite(radius) or radius<=0
                or any(abs(low[i]-(origin[i]-radius))>1e-8 or abs(high[i]-(origin[i]+radius))>1e-8 for i in range(3))):
            raise ValueError('Generated speed-sign component enclosure or pose differs')
        if any(re.match(r' Destroy '+str(actor)+r'\b',line) for line in originals['capture/recorder_info.txt'].read_text().splitlines()):
            raise ValueError('Derived static sign is not present throughout recording')
        for event in events.values():
            devices=[d for d in event['devices'] if d.get('actor_id')==actor]
            if len(devices)>1 or any(d.get('blueprint')!=row['blueprint'] or not _finite_vector(d.get('position_m')) or math.dist(d['position_m'],origin)>1e-6 for d in devices):
                raise ValueError('Recorded static speed-sign identity or pose differs')
        actors.add(actor);covered.add(key);bounds.append({'actor_id':actor,'low_m':low,'high_m':high})
    if not actors or covered!=set(signals):raise ValueError('Incomplete qualified source XML signal inventory')
    participants={int(k) for k,name in registry.items() if name.startswith(('vehicle.','walker.'))}
    for event in events.values():
        if ({p.get('actor_id') for p in event['participants']}!=participants
                or any(d.get('actor_id')not in actors for d in event['devices'])):
            raise ValueError('Unaccounted original opaque actor or device')
    return {frame:list(bounds) for frame in events},actors


def _check_reference_dependencies(references, checked, original_hashes=()):
    """Verify model dependencies; original data hashes terminate provenance traversal.

    Historical runtime links inside already verified original manifests are not
    dependencies of the declared reference model. Its actual model/source/asset
    contracts must be supplied explicitly and are recursively verified here.
    """
    import json
    from pathlib import Path
    seen = set()
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                key = (value['path'], value['sha256'])
                if key in seen:return
                seen.add(key)
                path = checked('reference-dependency-'+str(len(seen)), value)
                if Path(value['path']).suffix == '.json' and value['sha256'] not in original_hashes:
                    visit(json.loads(path.read_text()))
            else:
                for item in value.values():visit(item)
        elif isinstance(value, list):
            for item in value:visit(item)
    visit(references)


def _source_reference_component_models(certificate, originals, checked, registry, required_blueprints):
    """Consume hash-bound complete source-qualified render-reference assemblies."""
    import json
    reference = certificate.get('reference_vehicle_components')
    if reference is None:return {}
    from .reference_geometry import ReferenceComponentGeometry
    data = json.loads(checked('reference-vehicle-components.json', reference).read_text())
    if (data.get('schema') != 'source_bound_reference_vehicle_components_v1'
            or data.get('recording_id') != certificate['recording_id']):
        raise ValueError('Reference component recording identity differs')
    models = {}
    required = ('road.xodr', 'runner.py', 'capture/manifest.json',
                'capture/evidence.jsonl', 'capture/recorder_info.txt')
    for row in data.get('models', []):
        blueprint = row.get('blueprint')
        if not isinstance(blueprint, str) or not blueprint.startswith('vehicle.') or blueprint in models:
            raise ValueError('Duplicate or invalid reference model identity')
        q = json.loads(checked('reference-model-qualification-'+blueprint, row['qualification']).read_text())
        if (q.get('schema') != 'source_qualified_articulated_render_reference_v1'
                or q.get('recording_id') != certificate['recording_id']
                or q.get('blueprint') != blueprint
                or q.get('geometry_sha256') != row['geometry']['sha256']
                or q.get('complete_applicable_component_coverage') is not True
                or q.get('method_is_declared_geometry_reference_estimate') is not True
                or q.get('pose_source') != 'original_root_and_eight_body_corner_basis_v1'):
            raise ValueError('Incomplete reference component source qualification')
        for name in required:
            if (name not in originals or q.get('original_source_hashes', {}).get(name)
                    != certificate['original_sources'][name]['sha256']):
                raise ValueError('Reference component original source differs')
        references = q.get('source_references', {})
        if not all(name in references for name in ('asset_component_bindings', 'render_export',
                'configuration_coverage', 'root_transform_contract', 'wheel_travel_contract')):
            raise ValueError('Missing reference component coverage contract')
        _check_reference_dependencies(references, checked, {r['sha256'] for r in certificate['original_sources'].values()})
        geometry = ReferenceComponentGeometry.load(
            checked('reference-geometry-'+blueprint, row['geometry']), q.get('wheel_travel_bound_m'))
        if q.get('geometry_counts') != {'triangles': geometry.triangle_count,
                'door_envelopes': geometry.door_count, 'wheels': len(geometry.centers)}:
            raise ValueError('Reference geometry component inventory differs')
        support_reference = q.get('opaque_rigid_triangle_support')
        if support_reference is not None:
            import numpy as np
            support = json.loads(checked('opaque-triangle-qualification-'+blueprint,
                                         support_reference).read_text())
            if (support.get('schema') != 'source_qualified_matte_triangle_support_v1'
                    or support.get('recording_id') != certificate['recording_id']
                    or support.get('blueprint') != blueprint
                    or support.get('geometry_sha256') != row['geometry']['sha256']
                    or support.get('original_source_hashes') != q['original_source_hashes']
                    or support.get('opacity_convention') != 'asset_uv0_base_mip_bilinear_matte_v1'
                    or support.get('complete_material_binding') is not True
                    or support.get('whole_triangle_mask_support') is not True):
                raise ValueError('Unqualified opaque reference triangle support')
            refs = support.get('source_references', {})
            if not all(name in refs for name in ('sampler_binding', 'mask_shader',
                    'texture_export', 'source_uv_geometry', 'whole_triangle_support')):
                raise ValueError('Missing opaque reference material inputs')
            _check_reference_dependencies(refs, checked,
                {r['sha256'] for r in certificate['original_sources'].values()})
            cutoff = support.get('alpha_cutoff')
            if type(cutoff) not in (int, float) or not math.isfinite(cutoff) or not 0 <= cutoff < 1:
                raise ValueError('Invalid source material alpha cutoff')
            with np.load(checked('opaque-triangle-support-'+blueprint, support['arrays']),
                         allow_pickle=False) as arrays:
                if set(arrays.files) != {'triangle_indices', 'minimum_source_alpha'}:
                    raise ValueError('Invalid opaque triangle source arrays')
                indices, alpha = arrays['triangle_indices'], arrays['minimum_source_alpha']
                if (alpha.shape != indices.shape or alpha.dtype.kind not in 'iu'
                        or np.any(alpha > 255) or np.any(alpha < math.ceil(cutoff*255)+2)):
                    raise ValueError('Opaque triangle mask does not establish the cutoff')
                geometry.qualify_opaque_triangles(indices)
        material_reference = q.get('rigid_material_support')
        if material_reference is not None:
            import numpy as np
            material = json.loads(checked('rigid-material-qualification-'+blueprint,
                                          material_reference).read_text())
            if (material.get('schema') != 'source_qualified_rigid_materials_v1'
                    or material.get('recording_id') != certificate['recording_id']
                    or material.get('blueprint') != blueprint
                    or material.get('geometry_sha256') != row['geometry']['sha256']
                    or material.get('original_source_hashes') != q['original_source_hashes']
                    or material.get('reference_flags') != {
                        'mesh_reverse_culling': False, 'view_reverse_culling': False,
                        'view_two_sided': False, 'positive_transform_determinant': True}
                    or material.get('winding') != 'preserved_original_UE_native_order'):
                raise ValueError('Unqualified rigid material reference')
            refs = material.get('source_references', {})
            if not all(name in refs for name in ('material_binding', 'opaque_blend_contract',
                                                 'single_sided_contract', 'cull_parity')):
                raise ValueError('Missing rigid material source contracts')
            _check_reference_dependencies(refs, checked,
                {r['sha256'] for r in certificate['original_sources'].values()})
            glass = material.get('glass_transmission')
            if glass is not None and (
                    not isinstance(glass, dict)
                    or glass.get('alpha_formula') != 'I+(1-I)*max(1-NdotV,0.0001)^EXP'
                    or glass.get('normal_override') != [0, 0, 0, 1]
                    or not all(name in refs for name in ('glass_shader', 'glass_normals'))):
                raise ValueError('Unqualified source glass transmission convention')
            with np.load(checked('rigid-material-arrays-'+blueprint, material['arrays']),
                         allow_pickle=False) as arrays:
                expected_arrays = {'opaque_triangle_indices', 'single_sided_triangle_indices'}
                if glass is not None:
                    expected_arrays.update(('glass_triangle_indices', 'glass_vertex_normals'))
                if set(arrays.files) != expected_arrays:
                    raise ValueError('Invalid rigid material source arrays')
                opaque = arrays['opaque_triangle_indices']
                sides = arrays['single_sided_triangle_indices']
                geometry.qualify_single_sided_triangles(sides)
                if (opaque.ndim != 1 or opaque.dtype.kind not in 'iu'
                        or np.any(opaque < 0) or np.any(opaque >= geometry.triangle_count)
                        or np.any(opaque[1:] <= opaque[:-1])):
                    raise ValueError('Invalid opaque blend triangle subset')
                geometry.qualify_opaque_triangles(np.union1d(geometry.opaque_indices, opaque))
                if glass is not None:
                    if not set(map(int, arrays['glass_triangle_indices'])) <= geometry.single_sided_indices:
                        raise ValueError('Glass material sidedness is not qualified')
                    geometry.qualify_fresnel_transmission(arrays['glass_triangle_indices'],
                        arrays['glass_vertex_normals'], glass.get('intensity'), glass.get('exponent'))
        mask_reference = q.get('ray_local_mask_support')
        if mask_reference is not None:
            import numpy as np
            mask = json.loads(checked('ray-mask-qualification-'+blueprint, mask_reference).read_text())
            if (mask.get('schema') != 'source_qualified_matte_ray_mask_support_v1'
                    or mask.get('recording_id') != certificate['recording_id']
                    or mask.get('blueprint') != blueprint
                    or mask.get('geometry_sha256') != row['geometry']['sha256']
                    or mask.get('original_source_hashes') != q['original_source_hashes']
                    or mask.get('opacity_convention') != 'asset_uv0_base_mip_bilinear_matte_v1'
                    or mask.get('uv_orientation') != 'unflipped_image_rows'
                    or mask.get('complete_material_binding') is not True):
                raise ValueError('Unqualified ray-local reference mask support')
            refs = mask.get('source_references', {})
            if not all(name in refs for name in ('sampler_binding', 'mask_shader',
                    'texture_export', 'source_uv_geometry', 'uv_orientation', 'source_mask_construction')):
                raise ValueError('Missing ray-local reference material inputs')
            _check_reference_dependencies(refs, checked,
                {r['sha256'] for r in certificate['original_sources'].values()})
            with np.load(checked('ray-mask-arrays-'+blueprint, mask['arrays']), allow_pickle=False) as arrays:
                if set(arrays.files) != {'triangle_indices', 'triangle_uv', 'alpha'}:
                    raise ValueError('Invalid ray-local reference mask arrays')
                geometry.qualify_opaque_masks(arrays['triangle_indices'], arrays['triangle_uv'],
                                              arrays['alpha'], mask.get('alpha_cutoff'))
        models[blueprint] = geometry
    available = {name for name in registry.values() if name.startswith('vehicle.')}
    if not required_blueprints <= set(models) <= available:
        raise ValueError('Incomplete source vehicle reference model inventory')
    return models


def _source_vehicle_enclosures(certificate, originals, events, packet, checked, inventory, static_actors=()):
    """Qualify original API body enclosures; a hit is never a blocked answer."""
    import json,re
    from pathlib import Path
    reference = certificate.get('opaque_vehicle_enclosures')
    if reference is None:return None, None
    if certificate.get('opaque_enclosure_model') != 'original_vehicle_body_bbox_v1' or inventory is None:
        raise ValueError('Unqualified opaque body enclosure source')
    from .body_capture import acquisition_contract
    acquisition_contract(certificate, originals)
    if 'capture/recorder_info.txt' not in originals:raise ValueError('Missing full-period native actor census')
    registry={}
    for line in Path(originals['capture/recorder_info.txt']).read_text().splitlines():
        match=re.match(r' Create (\d+): (\S+) ',line)
        if match:registry[match[1]]=match[2]
    declared={key:value if isinstance(value,str)else value['name'] for key,value in certificate['native_actor_registry'].items()}
    if registry!=declared:raise ValueError('Opaque actor census differs from original Native source')
    opaque={int(key) for key,name in registry.items() if name!='spectator' and not name.startswith('sensor.')} - set(static_actors)
    if any(not registry[str(actor)].startswith('vehicle.') for actor in opaque):
        raise ValueError('Unsupported opaque actor body enclosure role')
    required_blueprints = {registry[str(actor)] for actor in opaque
                           for event in events.values() if actor != event['actor_id']}
    models = _source_reference_component_models(certificate, originals, checked, registry, required_blueprints)
    rows={}
    with checked('opaque-vehicle-enclosures.jsonl',reference).open() as source:
        for line in source:
            row=json.loads(line);ident=row['original_frame']
            if ident in rows:raise ValueError('Duplicate opaque enclosure frame')
            rows[ident]=row
    if set(rows)!=set(events):raise ValueError('Incomplete all-recording enclosure source inventory')
    selected = {frame['original_frame'] for frame in packet['frames']}
    result={}
    for ident,event in events.items():
        row=rows[ident];participants={p['actor_id']:p for p in event['participants']}
        bounds={b['actor_id']:b for b in row['bounds']}
        if (len(participants)!=len(event['participants']) or set(participants)!=opaque
                or len(bounds)!=len(row['bounds']) or set(bounds)!=opaque
                or row['actor_id']!=event['actor_id'] or row['recording_time_s']!=event['recording_time_s']):
            raise ValueError('Missing or inconsistent original opaque actor body')
        for actor,participant in participants.items():
            body=participant.get('body_vertices_m',[]);box=bounds[actor]
            if participant['blueprint']!=registry[str(actor)] or len(body)!=8 or any(not _finite_vector(p) for p in body):
                raise ValueError('Invalid original opaque actor body geometry')
            enlargement=64*(2.**-23)*max(1.,*(abs(v) for p in body for v in p))
            expected_low=[min(p[i] for p in body)-enlargement for i in range(3)]
            expected_high=[max(p[i] for p in body)+enlargement for i in range(3)]
            if box.get('low_m')!=expected_low or box.get('high_m')!=expected_high:
                raise ValueError('Opaque enclosure differs from original source body')
        # Original identity/body coverage remains recording-wide. Only packet
        # frames require observer queries or instantiate a reference model.
        if ident not in selected:
            result[ident] = [dict(bounds[actor]) for actor in participants
                             if actor != event['actor_id']]
            continue
        # Share the original body encoding budget. Each reference query adds
        # its own observer/local-coordinate budget and double-precision guard.
        source_margin = None
        if models:
            query_rows = [q for q in inventory.get('observer_query_frames', []) if q['original_frame'] == ident]
            if len(query_rows) != 1:raise ValueError('Missing reference component observer frame')
            positions = [p for lane in query_rows[0]['lanes'] for path in lane['paths']
                         for p in path['native_positions_m']]
            if not positions or any(not _finite_vector(p) for p in positions):
                raise ValueError('Invalid reference component observer positions')
            source_margin = 64*2**-23*max(1.,
                *(abs(x) for p in participants.values() for vertex in p['body_vertices_m'] for x in vertex),
                *(abs(x) for p in participants.values() for x in p['position_m']))
        # Build from verified source vertices only; ignore any packet-supplied axes.
        result[ident]=[]
        for actor, participant in participants.items():
            if actor == event['actor_id']:continue
            box = dict(bounds[actor])
            box.pop('_source_oriented_body', None)
            box.pop('_source_reference_components', None)
            if models:
                from .reference_geometry import ReferenceActorGeometry
                oriented = _source_body_oriented_enclosure(participant['body_vertices_m'])
                box['_source_reference_components'] = ReferenceActorGeometry(
                    models[participant['blueprint']], participant.get('position_m'),
                    oriented['axes'], source_margin)
            else:
                try:
                    box['_source_oriented_body'] = _source_body_oriented_enclosure(participant['body_vertices_m'])
                except ValueError:
                    pass  # A degenerate basis retains the verified axis-aligned bound.
            result[ident].append(box)
    query_frames=inventory.get('observer_query_frames',[]);queries={}
    if (inventory.get('observer_query_method')!='native_incoming_route_positions_v1'
            or inventory.get('observer_query_recording_frame_count')!=len(events)
            or len(query_frames)!=len({row['original_frame'] for row in query_frames})
            or not {frame['original_frame'] for frame in packet['frames']}
                   <= {row['original_frame'] for row in query_frames} <= set(events)):
        raise ValueError('Independent native observer frame scope differs')
    for row in query_frames:
        for lane in row['lanes']:
            for path in lane['paths']:
                key=(row['original_frame'],lane['lane_id'],tuple(path['branch_indices']))
                if key in queries:raise ValueError('Duplicate independent observer route')
                queries[key]=path['native_positions_m']
    return result,queries


def _enclosure_native_positions(queries, frame, lane, choices):
    if queries is None:return None
    key=(frame,lane,tuple(choice['selected_index_in_this_enumerated_path'] for choice in choices))
    if key not in queries:raise ValueError('Missing independently qualified native observer route')
    values=queries[key]
    if any(not _finite_vector(value) for value in values):raise ValueError('Invalid native observer positions')
    return values

def _source_static_mesh_api_enclosures(certificate, originals, events, checked, data):
    """Original visible-mesh API bounds: declared reference geometry estimate."""
    import json,re
    from pathlib import Path
    if (data.get('recording_id')!=certificate['recording_id']
            or data.get('schema')!='source_bound_static_mesh_render_API_enclosures_v1'):
        raise ValueError('Unqualified static mesh API source identity')
    qualification=json.loads(checked('static-mesh-qualification.json',data['source_qualification']).read_text())
    if (qualification.get('schema')!='source_qualified_static_mesh_render_API_enclosure_reference_estimate_v1'
            or qualification.get('recording_id')!=certificate['recording_id']
            or qualification.get('complete_applicable_visually_opaque_component_coverage')is not True
            or qualification.get('method_is_declared_geometry_reference_estimate')is not True):
        raise ValueError('Incomplete static mesh reference geometry qualification')
    measurement_source = qualification.get('measurement_source', 'actual_scene_identity.json')
    if measurement_source not in ('actual_scene_identity.json', 'native-physical-road-markings.json'):
        raise ValueError('Unsupported original static mesh measurement source')
    required=('road.xodr','runner.py','capture/manifest.json','capture/evidence.jsonl','capture/recorder_info.txt','trace.jsonl',measurement_source,'carla_recorder.log')
    for name in required:
        reference=qualification.get('source_refs',{}).get(name)
        if (name not in originals or not reference
                or reference['sha256']!=certificate['original_sources'][name]['sha256']):
            raise ValueError('Static mesh source map/input differs')
        checked('static-mesh-original-'+name,reference)
    if qualification['source_refs']['road.xodr']['sha256']!=certificate['xodr_sha256']:
        raise ValueError('Static mesh source map differs from certificate')
    contracts=qualification.get('reference_source_contracts',{})
    required_contracts={'StaticMeshFactory.cpp':'e23b3f654226b4eb57cc4f5b7306b2e87ab590e7de69c85e4f67b77aa291b76a',
        'BoundingBoxCalculator.cpp':'b0e6172473d7537ec48ee9ff7135cba4622f46f5ded0c15bcba1d678af028e20',
        'BoundingBox.h':'69d66c6879cf1eeaade922f5572c999a9ae076f6c3a908907329f599b23b186f'}
    for name,source_hash in required_contracts.items():
        if name not in contracts or contracts[name]['sha256']!=source_hash:
            raise ValueError('Unqualified static mesh reference API contract')
        checked('static-mesh-contract-'+name,contracts[name])
    manifest=json.loads(originals['capture/manifest.json'].read_text())
    if manifest.get('acquisition')!='original_live_run' or manifest.get('observation_contract_version')not in(2,3):
        raise ValueError('Unsupported original static mesh observation contract')
    registry_rows=re.findall(r' Create (\d+): (\S+) ',originals['capture/recorder_info.txt'].read_text())
    registry=dict(registry_rows)
    if len(registry_rows)!=len(registry):raise ValueError('Duplicate static mesh Native actor identity')
    declared={str(k):v if isinstance(v,str)else v['name']for k,v in certificate['native_actor_registry'].items()}
    if registry!=declared:raise ValueError('Static mesh Native census differs')
    rows=data.get('actors',[]);actors={r.get('actor_id')for r in rows}
    expected={int(k)for k,v in registry.items()if v.startswith('static.')}
    if len(rows)!=len(actors)or actors!=expected or not actors:
        raise ValueError('Incomplete static mesh actor component scope')
    identity=json.loads(originals[measurement_source].read_text())
    if measurement_source == 'native-physical-road-markings.json':
        tiles = identity.get('tiles')
        if not isinstance(tiles, list) or not tiles:
            raise ValueError('Incomplete original physical marking tile inventory')
        observed = []
        for tile in tiles:
            if tile.get('blueprint') != 'static.prop.mesh':
                raise ValueError('Unexpected physical marking actor role')
            observed.append(dict(tile, mesh_path=tile.get('asset'), scale=float(tile['scale']),
                                 body_vertices_native_m=tile.get('body_vertices_m')))
    else:
        observed = identity.values()
    measurements={}
    for item in observed:
        if isinstance(item,dict)and type(item.get('actor_id'))is int and 'body_vertices_native_m'in item:
            if item['actor_id']in measurements:raise ValueError('Duplicate original static mesh identity')
            measurements[item['actor_id']]=item
    native=json.loads(checked('static-mesh-native-packets.json',qualification['source_refs']['native_packets']).read_text())
    provenance=native.get('source_provenance',{})
    if provenance.get('schema')!='source_bound_native_packet_derivation_v1':
        raise ValueError('Unbound Native packet derivation')
    recorder=provenance.get('original_recorder',{});parser=provenance.get('parser_source',{})
    if (recorder.get('sha256')!=certificate['original_sources']['carla_recorder.log']['sha256']
            or parser.get('sha256')!='a5478888239fb1efe1128ca7219013cf61e8a90db0a215f558dfc333205ddaf2'):
        raise ValueError('Native packet recorder/parser source differs')
    checked('static-native-original-recorder',recorder);checked('static-native-parser-source',parser)
    original=json.loads(checked('static-native-original-packets',provenance['original_native_packets']).read_text())
    derived=json.loads(checked('static-native-derivation-receipt',provenance['derivation_receipt']).read_text())
    payload=dict(native);payload.pop('source_provenance')
    if (payload!=original or derived.get('recording_id')!=certificate['recording_id']
            or derived.get('all_native_packets')!=provenance['original_native_packets']
            or derived.get('parser')!=parser
            or derived.get('original_sources',{}).get('carla_recorder.log')!=recorder):
        raise ValueError('Native normalized payload or original derivation differs')
    native_ids=sorted(map(int,native.get('positions_cm',{})))
    ordered=sorted(events)
    if len(native_ids)!=len(ordered)or set(native.get('positions_cm',{}))!=set(native.get('rotations_deg',{})):
        raise ValueError('Incomplete static mesh full-period Native pose inventory')
    frame_info={row['frame']:row for row in native.get('frames',[])}
    if len(frame_info)!=len(native.get('frames',[]))or set(frame_info)!=set(native_ids):
        raise ValueError('Static mesh Native frame metadata differs')
    for index,ni in enumerate(native_ids):
        duration=frame_info[ni].get('duration_s')
        if index==len(native_ids)-1:
            if duration!=-1.:raise ValueError('Native final duration sentinel differs')
        elif (type(duration)not in(int,float)or not math.isfinite(duration)or duration<=0
                or abs(duration-(frame_info[native_ids[index+1]]['elapsed_s']-frame_info[ni]['elapsed_s']))>1e-5):
            raise ValueError('Native frame duration/elapsed join differs')
    first_time=events[ordered[0]]['recording_time_s']
    for ident,ni in zip(ordered,native_ids):
        pose=native['positions_cm'][str(ni)].get(str(events[ident]['actor_id']))
        elapsed=frame_info[ni].get('elapsed_s')
        if (not isinstance(pose,list)or len(pose)!=3 or not _finite_vector(pose)
                or max(abs(pose[j]/100-events[ident]['ego']['position_m'][j])for j in range(3))>1e-5
                or type(elapsed)not in(int,float)or not math.isfinite(elapsed)
                or abs(elapsed+first_time-events[ident]['recording_time_s'])>1e-5):
            raise ValueError('Static mesh Native/original frame join differs')
    frame_offset=ordered[0]-native_ids[0];bounds=[]
    for row in rows:
        actor=row['actor_id'];key=str(actor);measurement=measurements.get(actor);description=native.get('actors',{}).get(key,{});attrs=description.get('attributes',{})
        scale=row.get('uniform_scale');spawn=row.get('spawn_native_m');vertices=measurement.get('body_vertices_native_m',[])if measurement else[]
        if (registry.get(key)!='static.prop.mesh'or description.get('name')!='static.prop.mesh'
                or measurement is None or attrs.get('mesh_path')!=measurement.get('mesh_path')
                or row.get('mesh_path')!=measurement.get('mesh_path')
                or measurement.get('scale',scale)!=scale
                or type(scale)not in(int,float)or not math.isfinite(scale)or scale<=0
                or float(attrs.get('scale','nan'))!=scale or float(attrs.get('mass','nan'))!=0
                or not _finite_vector(spawn)or len(vertices)!=8 or any(not _finite_vector(p)for p in vertices)):
            raise ValueError('Static mesh identity/scale/component bounds differ')
        center=[sum(p[j]for p in vertices)/8 for j in range(3)]
        extent=[(max(p[j]for p in vertices)-min(p[j]for p in vertices))/2 for j in range(3)]
        if any(x<=0 for x in extent):raise ValueError('Empty static mesh API enclosure')
        corrected=[spawn[j]+scale*(center[j]-spawn[j])for j in range(3)]
        hull=vertices+[[corrected[j]+sign[j]*extent[j]for j in range(3)]for sign in [(a,b,c)for a in(-1,1)for b in(-1,1)for c in(-1,1)]]+[spawn]
        pad=64*2**-23*max(1.,*(abs(x)for p in hull for x in p))
        low=[min(p[j]for p in hull)-pad for j in range(3)];high=[max(p[j]for p in hull)+pad for j in range(3)]
        if row.get('low_m')!=low or row.get('high_m')!=high:
            raise ValueError('Static mesh API enclosure differs from measured source')
        for ident,ni in zip(ordered,native_ids):
            pose=native['positions_cm'][str(ni)].get(key);rotation=native['rotations_deg'][str(ni)].get(key)
            if (ident!=ni+frame_offset or not isinstance(pose,list)or len(pose)!=3
                    or any(type(x)not in(int,float)or not math.isfinite(x)for x in pose)
                    or max(abs(pose[j]/100-spawn[j])for j in range(3))>1e-6
                    or rotation!=[0.,0.,0.]):
                raise ValueError('Static mesh reference pose/frame/rotation differs')
        bounds.append({'actor_id':actor,'low_m':low,'high_m':high})
    return {ident:list(bounds)for ident in events},actors


def _named_stock_prop_graph_source(certificate, sources, name):
    reference=sources.get(name)
    original=certificate.get('original_sources',{}).get(name)
    if not reference or not original or reference.get('sha256')!=original.get('sha256'):
        raise ValueError('Named prop graph is not bound to original capture')
    return reference

def _named_stock_prop_scope(registry, subject, definitions, rows):
    subjects=[int(k)for k,v in registry.items()if v.startswith('vehicle.')]
    if subjects!=[subject]:raise ValueError('Named prop subject/other participant differs')
    for key,name in registry.items():
        if name in definitions or int(key)==subject and name.startswith('vehicle.')or name=='spectator'or name.startswith('sensor.'):
            continue
        raise ValueError('Unaccounted named prop opaque actor role')
    expected={int(k)for k,v in registry.items()if v in definitions}
    if len(rows)!=len({x.get('actor_id')for x in rows})or {x.get('actor_id')for x in rows}!=expected:
        raise ValueError('Incomplete named prop actor scope')

def _named_stock_prop_graph_producer(manifest, generator_digest):
    # The pinned producer also emitted unversioned original captures. Identify
    # those by source bytes; never manufacture a version in retained evidence.
    versioned='observation_contract_version'in manifest
    if (manifest.get('acquisition')!='original_live_run'
            or manifest.get('generator_source',{}).get('sha256')!=generator_digest
            or versioned and manifest['observation_contract_version']not in(2,3)):
        raise ValueError('Unsupported named prop graph producer')

def _named_stock_prop_sdk_position(position_cm):
    """Location.h: float centimetres times 1e-2f, returned as SDK floats."""
    import struct
    def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
    scale=f32(.01)
    return [f32(value*scale)for value in position_cm]

def _source_named_stock_prop_api_enclosures(certificate, originals, events, checked, data):
    """Named stock props under the pinned StaticMeshActor reference factory."""
    import json,math,struct,re
    from .native_graph_motion import decode,reduction,dtype,vector
    expected_refs={
        'factory_uasset':'2c0b827636da3b486a7b3da9b97ed82e985c869af383b5688027b60f74e8835d',
        'factory_uexp':'2433ef4d77746f8542b9092e8c721bf72657b4c0642f4f0babf8264ea4380581',
        'decoded_factory':'47e746c747f29cf15397880bfbdf3a8b04e170a2643ae0574ade9fa3b16678a4',
        'definition_source':'be7bc456e3f74010ee7fa2f6e380736b20c296e545b7c410d3e354d4aa07c612',
        'BoundingBoxCalculator.cpp':'b0e6172473d7537ec48ee9ff7135cba4622f46f5ded0c15bcba1d678af028e20',
        'BoundingBox.h':'69d66c6879cf1eeaade922f5572c999a9ae076f6c3a908907329f599b23b186f',
        'generator':'82608c7cb8691c563120d888afe5d75d0f781a87ffa869ff3a8d4713252beaf2',
        'generator_utils':'d2f9845c53dff4c5c012995c844f0cf870e40a577f87f1dcbbd6d94676ec4863'}
    if data.get('recording_id')!=certificate['recording_id']:
        raise ValueError('Named prop source identity differs')
    q=json.loads(checked('named-prop-qualification',data['source_qualification']).read_text())
    if (q.get('schema')!='source_qualified_named_stock_prop_API_reference_v1'
            or q.get('recording_id')!=certificate['recording_id']
            or q.get('method_is_declared_geometry_reference_estimate')is not True):
        raise ValueError('Unqualified named prop reference scope')
    refs=q.get('reference_source_contracts',{})
    for name,digest in expected_refs.items():
        if refs.get(name,{}).get('sha256')!=digest:raise ValueError('Named prop reference contract differs')
        checked('named-prop-contract-'+name,refs[name])
    factory=json.loads(checked('named-prop-factory',refs['decoded_factory']).read_text())
    definitions={}
    for key,value in factory['Exports'][4]['Data'][0]['Value']:
        name=key['Value'].lower()
        if name in definitions:raise ValueError('Ambiguous named prop definition')
        fields={x['Name']:x['Value']for x in value['Value']};mesh=factory['Imports'][-fields['Mesh']-1]
        definitions[name]=factory['Imports'][-mesh['OuterIndex']-1]['ObjectName']+'.'+mesh['ObjectName']
    sources=q.get('source_refs',{})
    required=('road.xodr','runner.py','trace.jsonl','capture/manifest.json','capture/evidence.jsonl','capture/recorder_info.txt','capture/native/frames.jsonl','carla_recorder.log')
    for name in required:
        if (name not in originals or sources.get(name,{}).get('sha256')!=certificate['original_sources'].get(name,{}).get('sha256')):
            raise ValueError('Named prop original source differs')
        checked('named-prop-original-'+name,sources[name])
    manifest=json.loads(originals['capture/manifest.json'].read_text())
    _named_stock_prop_graph_producer(manifest,expected_refs['generator'])
    if sources['road.xodr']['sha256']!=certificate['xodr_sha256']:raise ValueError('Named prop map differs')
    text=originals['capture/recorder_info.txt'].read_text();adds=re.findall(r' Create (\d+): (\S+) ',text);registry=dict(adds)
    if len(adds)!=len(registry)or re.search(r' Destroy \d+',text):raise ValueError('Named prop census is not closed/static')
    declared={str(k):v if isinstance(v,str)else v['name']for k,v in certificate['native_actor_registry'].items()}
    if registry!=declared:raise ValueError('Named prop census differs')
    rows=data.get('actors',[]);byactor={r['actor_id']:r for r in rows};static={int(k)for k,v in registry.items()if v.startswith('static.')}
    if len(rows)!=len(byactor)or set(byactor)!=static or not static:raise ValueError('Incomplete named prop scope')
    for actor,row in byactor.items():
        if registry[str(actor)]not in definitions or row.get('blueprint')!=registry[str(actor)]or row.get('mesh_path')!=definitions[registry[str(actor)]]:
            raise ValueError('Named prop factory identity differs')
    derivation=json.loads(checked('named-prop-native-derivation',q['native_derivation']).read_text())
    if (derivation.get('recording_id')!=certificate['recording_id'] or derivation.get('native_packets')!=q['native_packets'] or derivation.get('recorder')!=sources['carla_recorder.log']
            or derivation.get('parser',{}).get('sha256')!='a5478888239fb1efe1128ca7219013cf61e8a90db0a215f558dfc333205ddaf2'):
        raise ValueError('Unbound named prop Native derivation')
    checked('named-prop-native-parser',derivation['parser'])
    original_events={x['original_frame']:x for x in map(json.loads,originals['capture/evidence.jsonl'].read_text().splitlines())}
    if set(original_events)!=set(events):raise ValueError('Named prop original event inventory differs')
    for ident,event in events.items():
        original=original_events[ident]
        if (original['actor_id']!=event['actor_id']or original['recording_time_s']!=event['recording_time_s']
                or original['ego']['position_m']!=event['ego']['position_m']
                or original['ego']['body_vertices_m']!=event['ego']['body_vertices_m']):
            raise ValueError('Named prop original event/body differs')
    events=original_events
    native=json.loads(checked('named-prop-native-packets',q['native_packets']).read_text())
    if {str(k):v['name']for k,v in native['actors'].items()}!=registry:raise ValueError('Native named prop registry differs')
    native_ids=sorted(map(int,native['positions_cm']));ordered=sorted(events)
    if len(native_ids)!=len(ordered):raise ValueError('Incomplete Native named prop period')
    frame_offset=ordered[0]-native_ids[0]
    native_frames={x['frame']:x for x in native['frames']}
    if set(native_frames)!=set(native_ids):raise ValueError('Native named prop frame metadata differs')
    subject_ids={x['actor_id']for x in events.values()}
    if len(subject_ids)!=1:raise ValueError('Named prop subject is ambiguous')
    _named_stock_prop_scope(registry,next(iter(subject_ids)),definitions,rows)
    graphs={x['frame']:x for x in map(json.loads,originals['capture/native/frames.jsonl'].read_text().splitlines())}
    constant={};seen=set()
    def vertices(value):
        name,args=reduction(value)
        if name not in[('numpy.core.numeric','_frombuffer'),('numpy._core.numeric','_frombuffer')]or len(args)!=4 or args[2]!=(8,3)or args[3]!='C'or not isinstance(args[0],bytes)or len(args[0])!=192:
            raise ValueError('Invalid original named prop 3D geometry')
        vals=struct.unpack(dtype(args[1])+'24d',args[0])
        if any(not math.isfinite(v)for v in vals):raise ValueError('Nonfinite named prop geometry')
        return [list(vals[i:i+3])for i in range(0,24,3)]
    for ident,event in sorted(events.items()):
        if event['actor_id']!=next(iter({x['actor_id']for x in events.values()})):raise ValueError('Subject identity differs')
        if any(v.startswith(('vehicle.','walker.'))and int(k)!=event['actor_id']for k,v in registry.items()):raise ValueError('Other opaque participant unaccounted')
        ni=ident-frame_offset;pose=native['positions_cm'].get(str(ni),{}).get(str(event['actor_id']));elapsed=native_frames.get(ni,{}).get('elapsed_s')
        if (pose is None or max(abs(pose[j]/100-event['ego']['position_m'][j])for j in range(3))>1e-5
                or type(elapsed)not in(int,float)or not math.isfinite(elapsed)
                or abs(elapsed+events[ordered[0]]['recording_time_s']-event['recording_time_s'])>1e-5):
            raise ValueError('Native named prop subject/frame clock differs')
        frame=graphs[event['replay_frame']];name='capture/native/'+frame['base']
        reference=_named_stock_prop_graph_source(certificate,sources,name)
        root=decode(checked('named-prop-graph-'+str(ident),reference).read_bytes());kind,args=reduction(root)
        if kind!=('networkx.classes.digraph','DiGraph')or args!=()or root.state['graph']['frame']!=ident or abs(root.state['graph']['simulation_time_s']-event['replay_simulation_time_s'])>1e-6:
            raise ValueError('Named prop graph frame differs')
        found={};ego=[]
        for label,attrs in root.state['_node'].items():
            if not isinstance(attrs,dict):continue
            actor=attrs.get('carla_id',attrs.get('entity_id'))
            if actor==event['actor_id']and label=='ego':ego.append(vertices(attrs['threedbbox']))
            if actor not in byactor:continue
            if (actor in found or attrs.get('carla_id')!=actor or attrs.get('entity_id')!=actor
                    or attrs.get('sem_class')!=registry[str(actor)]or attrs.get('geometry_capture_scope')!='spawned_traffic_prop_independent_of_crop_and_occlusion'):
                raise ValueError('Named prop original actor geometry scope differs')
            body=vertices(attrs['threedbbox']);spawn=vector(attrs['vertex']);hull=body+[spawn]
            ni=ident-frame_offset;pose=native['positions_cm'].get(str(ni),{}).get(str(actor));rotation=native['rotations_deg'].get(str(ni),{}).get(str(actor))
            if pose is None or _named_stock_prop_sdk_position(pose)!=spawn or rotation!=[0.,0.,0.]:raise ValueError('Native named prop pose differs')
            pad=64*2**-23*max(1.,*(abs(x)for p in hull for x in p));bounds={'low_m':[min(p[j]for p in hull)-pad for j in range(3)],'high_m':[max(p[j]for p in hull)+pad for j in range(3)]}
            if any(byactor[actor].get(k)!=v for k,v in bounds.items()):raise ValueError('Named prop enclosure differs')
            if actor in constant and constant[actor]!=body:raise ValueError('Moving named prop is unsupported')
            constant[actor]=body;found[actor]=bounds
        if set(found)!=static or len(ego)!=1 or ego[0]!=event['ego']['body_vertices_m']:raise ValueError('Incomplete named prop/body graph join')
        seen.add(ident)
    if len(seen)!=len(events)or set(constant)!=static:raise ValueError('Incomplete named prop period')
    return {ident:[{'actor_id':r['actor_id'],'low_m':r['low_m'],'high_m':r['high_m']}for r in rows]for ident in events},static
