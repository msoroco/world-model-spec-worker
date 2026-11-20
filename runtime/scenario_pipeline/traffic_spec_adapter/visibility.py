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
            if low < probe <= high and not (high == probe and approach.get('any_sample_clear_at_probe') is False):
                return None, 'visibility bracket straddles declared probe'
            value = low  # Clear-side bound, never the uncertain midpoint.
        elif h.get('bound') == 'at_least':
            value = h.get('distance_m')
            # Do not use an unfinished search to classify the declared probe.
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid visibility search bound')
            if value < probe:
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
                   search_censored=any(a['any_body_sight_horizon']['bound']=='at_least' for a in approaches),
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
        elevated,upper=_constant_native_ground_ceiling(xml)
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
    tree=ast.parse(Path(originals['runner.py']).read_text())
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
    if isinstance(wall,ast.Constant)and type(wall.value)in(int,float):
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
                or not _source_curb_face_queries(originals,setup)):
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
    if (lane.get('all_paths_complete_and_clear') is not True
            or not isinstance(paths, list) or not 1 <= len(paths) <= 64):
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


def _analytic_route_samples(route, observations, distances, samples, ceiling, eye, maximum, map_digest, enclosures=(), native_positions=None):
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
        gaps = [min(observer[2], samples[i][2]) - ceiling for i in indices]
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
    for name in ('road.xodr','runner.py','capture/manifest.json','capture/evidence.jsonl','capture/native_map_facts.json','carla_recorder.log'):
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
    if (xml.findall('./road/objects/*') or xml.findall('./road/signals/signalReference')
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
    source_events={}
    with originals['capture/evidence.jsonl'].open() as source:
        for line in source:
            if not line.strip():continue
            event=json.loads(line);frame=event['original_frame']
            if frame in source_events:raise ValueError('Duplicate original visibility frame')
            source_events[frame] = {'actor_id': event['actor_id'], 'recording_time_s': event['recording_time_s'],
                                    'ego': {'body_vertices_m': event['ego']['body_vertices_m'],
                                            'position_m': event['ego']['position_m']},
                                    'participants': event.get('original_observations', {}).get('participants', []),
                                    'devices': event.get('original_observations', {}).get('devices', [])}
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
    selected_ids = {f['original_frame'] for f in frames}
    if (len(retained)!=len(table['frames']) or len(frames)!=packet['frame_count'] or len(selected_ids)!=len(frames)
            or set(retained)!=set(source_events) or not selected_ids<=set(retained)):
        raise ValueError('Analytical visibility frame inventory differs')
    if vehicle_enclosures is None:
        if selected_ids!=set(retained):raise ValueError('Analytical visibility frame inventory differs')
    elif (packet.get('frame_scope')!='verified_clear_subset' or packet.get('recording_frame_count')!=len(retained)):
        raise ValueError('Forged or unspecified partial clear frame scope')
    unknown = {f['original_frame'] for f in frames if any(lane.get('state') != 'at_least' for lane in f['required_lane_results'])}
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
            expected_branches = sorted(lane['lane_id'] for lane in lanes if lane.get('state') != 'at_least')
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
                    provenance['selection_policy'] = 'all actual native paths; numeric result invariant'
                    samples_on_path = []
                    for probe_sample in path['probes']:
                        observer = probe_sample.get('observer_m')
                        if not _finite_vector(observer):
                            raise ValueError('Incomplete native branch observer')
                        indices = [i for i, point in enumerate(samples)
                                   if min(observer[2], point[2]) > ceiling and not any(_segment_intersects_enclosure(observer, point, box) for box in (enclosures or {}).get(ident, []))]
                        samples_on_path.append({'distance_m': probe_sample['distance_m'],
                                                'observer_m': observer, 'clear_sample_indices': indices,
                                                'minimum_proved_vertical_clearance_m': probe_sample.get('positive_vertical_clearance_m')})
                    _analytic_route_samples(provenance, samples_on_path, distances, samples, ceiling, eye,
                                            maximum, packet['xodr']['sha256'], (enclosures or {}).get(ident, []),
                                            _enclosure_native_positions(native_queries, ident, lane['lane_id'], path['branch_choices']))
                    alternatives.append(provenance)
                    proofs.append({'branch_choices': path['branch_choices'], 'observer_route': provenance,
                                   'analytic_sample_certificates': samples_on_path})
                approaches.append({'lane_id': lane['lane_id'], 'observer_routes': alternatives,
                                   'any_sample_clear_at_probe': True,
                                   'any_body_sight_horizon': {'bound': 'at_least', 'distance_m': maximum},
                                   'native_branch_paths': proofs})
                continue
            if (lane['road_id']!=frame['native_road_id']or lane.get('state')!='at_least'or lane.get('distance_m')!=maximum
                    or lane.get('search_limit_m')!=maximum):
                raise ValueError('Analytical route/search coverage incomplete')
            _analytic_route_samples(route, observations, distances, samples, ceiling, eye,
                                    maximum, packet['xodr']['sha256'], (enclosures or {}).get(ident, []),
                                    _enclosure_native_positions(native_queries, ident, lane['lane_id'], []))
            approaches.append({'lane_id':lane['lane_id'],'observer_route':route,'any_sample_clear_at_probe':True,
                'any_body_sight_horizon':{'bound':'at_least','distance_m':maximum},'analytic_sample_certificates':observations})
        visibility={'method':ANALYTIC_METHOD,'distance_convention':TERMINAL_CONVENTION,'visibility_criterion':'any_of_nine_body_samples',
            'actual_actor_origin_m':frame['ego_position_m'],'ego_projection':{'road_id':frame['native_road_id'],'lane_id':frame['native_lane_id'],'s_m':station},
            'ego_body_samples_m':samples,'eye_height_m':eye,'probe_distance_m':probe,'maximum_search_distance_m':maximum,
            'maximum_observer_route_distance_m':max(probe,maximum),'scan_step_m':step,'horizon_tolerance_m':tolerance,
            'required_lane_ids':required,'approaches':approaches,'analytic_source':{'schema':'verified_source_bound_analytic_reference_v1',
                'source_inputs_verified':True,'no_cast_ray_executed':True,'packet_sha256':packet_digest,
                'certificate_sha256':certificate_digest,'retained_frames_sha256':frames_digest,
                'generated_road_geometry_upper_z_m':ceiling,'source_model':certificate['source_model']}}
        if static_enclosures is not None:
            visibility['analytic_source']['opaque_static_enclosures_sha256']=certificate['opaque_static_enclosures']['sha256']
            visibility['analytic_source']['static_pose_source']='derived_static'
        if vehicle_enclosures is not None:
            visibility['analytic_source']['opaque_vehicle_enclosures_sha256'] = certificate['opaque_vehicle_enclosures']['sha256']
            visibility['analytic_source']['frame_scope'] = 'verified_clear_subset'
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


def _segment_intersects_enclosure(a, b, box):
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
    return True


def _source_generated_speed_sign_enclosures(certificate, originals, events, xml, checked):
    """Consume complete source-qualified component bounds, never trigger boxes.

    Asset decoding/qualification belongs to the producer, not this exporter.
    All source identities, declarations, poses and bounds remain hash-bound.
    """
    import json,re
    reference=certificate.get('opaque_static_enclosures')
    if reference is None:return None,set()
    data=json.loads(checked('opaque-static-enclosures.json',reference).read_text())
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


def _source_vehicle_enclosures(certificate, originals, events, packet, checked, inventory, static_actors=()):
    """Qualify original API body enclosures; a hit is never a blocked answer."""
    import json,re
    from pathlib import Path
    reference = certificate.get('opaque_vehicle_enclosures')
    if reference is None:return None, None
    if certificate.get('opaque_enclosure_model') != 'original_vehicle_body_bbox_v1' or inventory is None:
        raise ValueError('Unqualified opaque body enclosure source')
    manifest = json.loads(Path(originals['capture/manifest.json']).read_text())
    if manifest.get('acquisition')!='original_live_run' or manifest.get('observation_contract_version')not in (2,3):
        raise ValueError('Unsupported original body acquisition contract')
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
    rows={}
    with checked('opaque-vehicle-enclosures.jsonl',reference).open() as source:
        for line in source:
            row=json.loads(line);ident=row['original_frame']
            if ident in rows:raise ValueError('Duplicate opaque enclosure frame')
            rows[ident]=row
    if set(rows)!=set(events):raise ValueError('Incomplete all-recording enclosure source inventory')
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
        result[ident]=[box for actor,box in bounds.items() if actor!=event['actor_id']]
    query_frames=inventory.get('observer_query_frames',[]);queries={}
    if (inventory.get('observer_query_method')!='native_incoming_route_positions_v1'
            or inventory.get('observer_query_recording_frame_count')!=len(events)
            or len(query_frames)!=len(packet['frames'])
            or {row['original_frame'] for row in query_frames}!={frame['original_frame'] for frame in packet['frames']}):
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
