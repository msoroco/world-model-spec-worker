"""Same-frame physical evidence projections. No legal thresholds or conclusions."""
import math,json,xml.etree.ElementTree as ET
from geometry import overlaps

def xyz(p):return [p.x,p.y,p.z]
def norm(v):return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def polygon(points):
    # Native crosswalk output repeats polygon start between groups.
    result=[];current=[]
    for p in points:
        value=[p.x,p.y]
        if current and value==current[0]:
            if len(current)>2:result.append(current)
            current=[]
        else:current.append(value)
    if len(current)>2:result.append(current)
    return result

def devices(world,mapping):
    landmarks=[]
    for mark in mapping.get_all_landmarks():
        lanes=[{'from_lane':v.from_lane,'to_lane':v.to_lane} for v in mark.get_lane_validities()]
        landmarks.append({'id':mark.id,'type':mark.type,'road_id':mark.road_id,'s_m':mark.s,'orientation':str(mark.orientation),'lane_validity':lanes,'position_m':xyz(mark.transform.location)})
    actors=[]
    for actor in world.get_actors():
        if actor.type_id.startswith('traffic.'):
            item={'actor_id':actor.id,'blueprint':actor.type_id,'position_m':xyz(actor.get_transform().location)}
            if hasattr(actor,'get_state'):item['indication']=str(actor.get_state())
            if hasattr(actor,'get_affected_lane_waypoints'):item['governed_lanes']=[[w.road_id,w.lane_id] for w in actor.get_affected_lane_waypoints()]
            actors.append(item)
    return {'landmarks':landmarks,'actors':actors}

def setup(world,c,a):
    """Verify generated native feature readback; authored metadata alone is insufficient."""
    import carla
    mapping=world.get_map();readback=mapping.to_opendrive();root=ET.fromstring(readback)
    inventory=devices(world,mapping);crosswalks=polygon(mapping.get_crosswalks());kind=c['mechanism'];checks=[]
    if kind=='yield':
        marks=[m for m in inventory['landmarks'] if m['type']=='205' and m['road_id']==1 and any(v['from_lane']<=-1<=v['to_lane'] or v['to_lane']<=-1<=v['from_lane'] for v in m['lane_validity'])]
        native=[x for x in inventory['actors'] if 'yield' in x['blueprint'].lower()]
        # CARLA releases without a yield-sign actor cannot claim a physically erected sign.
        if not marks or not native:raise RuntimeError('external_asset: generated yield signal type205 has no verified native yield-sign actor/governed approach; provide supported native yield asset/map')
        wp=mapping.get_waypoint_xodr(1,-1,489.)
        nexts=wp.next(3.) if wp else []
        if not nexts or not any(p.is_junction for p in nexts):raise RuntimeError('live_measurement: native governed incoming lane does not enter authored junction')
        checks.append({'target':'yield_feature','requested':True,'measured':True,'source':'native landmark205 lane validity + traffic.yield actor + native incoming waypoint'})
        if crosswalks:raise RuntimeError('live_measurement: fallback branch requires no crosswalk; native map reports crosswalks')
    if kind=='reverse' and not crosswalks:raise RuntimeError('external_asset: OpenDRIVE crosswalk object did not yield native crosswalk geometry; supply supported native crossing mesh/map')
    # Capture native environment inventory separately from authored legal/context assumptions.
    env=[]
    for label in (carla.CityObjectLabel.TrafficSigns,carla.CityObjectLabel.TrafficLight):
        env.extend([{'id':o.id,'name':o.name,'label':str(label),'position_m':xyz(o.transform.location)} for o in world.get_environment_objects(label)])
    return {'native_map':mapping.name,'devices':inventory,'crosswalk_polygons':crosswalks,'environment_controls':env,'readback_signal_count':len(root.findall('.//signal')),'checks':checks,'authored_context_is_synthetic':True}

def ordered_states(participants,observations):
    """Join actual same-frame records by actor ID; inventory order is not actor order."""
    index={}
    for state in observations:
        ident=state['actor_id']
        if ident in index:raise ValueError('Duplicate original participant actor ID')
        index[ident]=state
    if any(actor.id not in index for actor in participants):raise ValueError('Missing original required participant')
    return [index[actor.id] for actor in participants]

def validate_visibility(value,expected=None):
    if not value or value.get('unknown_reason'):raise ValueError('Missing actual actor visibility')
    approaches=value.get('approaches',[]);required=set(value.get('required_lane_ids',[]))
    if not required or required!={entry['lane_id'] for entry in approaches}:raise ValueError('Incomplete incoming approach set')
    if expected is not None and required!=set(expected):raise ValueError('Both declared incoming directions are required')
    for entry in approaches:
        horizon=entry.get('any_body_sight_horizon',{})
        if entry.get('unknown_reason') or len(entry.get('body_rays_at_probe',[]))!=9 or horizon.get('unknown') or horizon.get('bound') not in ('first_sampled_occlusion','at_least'):raise ValueError('Incomplete nine-point approach horizon')
        if horizon['bound']=='at_least' and horizon.get('distance_m',0)<230:raise ValueError('Incomplete full search extent')
    return True

def project(world,ego,participants,c,a,previous,event=None):
    import carla
    from original_observations import actor_state,visible_relation
    mapping=world.get_map();t=ego.get_transform();v=ego.get_velocity();h=math.radians(t.rotation.yaw);forward=(math.cos(h),math.sin(h));states=(ordered_states(participants,event['original_observations']['participants']) if event else [actor_state(p) for p in participants]);subject=next(s for s in states if s['actor_id']==ego.id);body=subject['body_vertices_m'];footprint=[[p[0],p[1]] for p in body]
    # Convex hull avoids duplicated upper/lower body vertices and native corner order.
    from shapely.geometry import MultiPoint
    footprint=[list(p) for p in MultiPoint(footprint).convex_hull.exterior.coords][:-1]
    wp=mapping.get_waypoint(t.location);native_devices=devices(world,mapping);crosswalks=polygon(mapping.get_crosswalks());junctions={}
    for road,station in ((1,489.),(3,489.),(4,1.)):
        w=mapping.get_waypoint_xodr(road,-1,station)
        if w:
            for n in w.next(3.):
                if n.is_junction:
                    j=n.get_junction();corners=j.bounding_box.get_world_vertices(carla.Transform());junctions[str(j.id)]=[[p.x,p.y,p.z] for p in corners]
    native_polygons=[]
    for vertices in junctions.values():native_polygons.append([list(p) for p in MultiPoint([(p[0],p[1]) for p in vertices]).convex_hull.exterior.coords][:-1])
    subject_lane={'road_id':wp.road_id,'lane_id':wp.lane_id,'s_m':wp.s,'is_junction':wp.is_junction} if wp else {'status':'outside_native_driving_lanes'}
    relative=[]
    for actor,state in zip(participants,states):
        if actor.id==ego.id:continue
        dx=state['position_m'][0]-t.location.x;dy=state['position_m'][1]-t.location.y;along=dx*forward[0]+dy*forward[1];distance=math.hypot(dx,dy);old=previous.get(str(actor.id),distance);relative.append({'actor_id':actor.id,'relative_along_m':along,'distance_m':distance,'distance_change_m':distance-old,'heading_dot':math.cos(math.radians(state['heading_deg']-t.rotation.yaw)),'velocity_mps':state['velocity_mps'],'body_vertices_m':state['body_vertices_m']});previous[str(actor.id)]=distance
    directions=[]
    if wp:
        directions.append({'road_id':wp.road_id,'lane_id':wp.lane_id,'heading_deg':wp.transform.rotation.yaw})
        for getter in ('get_left_lane','get_right_lane'):
            side=getattr(wp,getter)();seen=set()
            while side and (side.road_id,side.lane_id) not in seen:
                seen.add((side.road_id,side.lane_id))
                if side.lane_type==carla.LaneType.Driving and math.cos(math.radians(side.transform.rotation.yaw-wp.transform.rotation.yaw))>.9:directions.append({'road_id':side.road_id,'lane_id':side.lane_id,'heading_deg':side.transform.rotation.yaw})
                side=getattr(side,getter)()
    # Absolute measured signed body gap uses actual world bounding box vertices.
    gap=[]
    for state in states:
        if state['actor_id']==ego.id:continue
        front=max(p[0]*forward[0]+p[1]*forward[1] for p in body);rear=min(p[0]*forward[0]+p[1]*forward[1] for p in state['body_vertices_m']);gap.append({'actor_id':state['actor_id'],'surface_gap_m':rear-front})
    dev=lambda token:[x for x in native_devices['actors'] if token in x['blueprint'].lower()]
    record={
      'kin.position':{'x':t.location.x,'y':t.location.y,'z':t.location.z},'kin.heading':t.rotation.yaw,'kin.speed':norm(v),'kin.extent':[{'actor_id':p.id,'width_m':2*p.bounding_box.extent.y,'length_m':2*p.bounding_box.extent.x,'world_vertices_m':s['body_vertices_m']} for p,s in zip(participants,states)],
      'dev.stop_sign':{'native_actors':dev('stop'),'native_landmarks':[x for x in native_devices['landmarks'] if x['type']=='206']},
      'dev.yield_sign':{'native_actors':dev('yield'),'native_landmarks':[x for x in native_devices['landmarks'] if x['type']=='205']},
      'dev.governs':native_devices,'dev.traffic_signal':{'native_actors':dev('traffic_light'),'indications_sampled_this_frame':True},
      'dev.human_direction':{'authored_officer_control':a.get('officer_control',{}).get('value',False),'pedestrian_actor_inventory':[{'actor_id':p.id,'blueprint':p.type_id} for p in world.get_actors() if p.type_id.startswith('walker.')],'authority_inferred':False},
      'st.lane_enters':{'subject_native_lane':subject_lane,'junctions':junctions},'st.stop_line':{'native_map_signal_inventory':native_devices['landmarks'],'authored_stop_line':a.get('stop_line',{}).get('value',False),'method':'native readback plus retained authored absence; no absence from graph crop'},'st.crosswalk':{'native_polygons':crosswalks},
      'drv.stopped':{'speed_mps':norm(v),'stationary_within_0_01mps_engineering':norm(v)<.01},
      'drv.priority_roadway':{'authored_through_highway':a.get('through_highway',{}).get('value',False),'provenance':'synthetic test context, no official road authority inferred','native_lane':subject_lane},
      'drv.entering_intersection':{'native_regions':native_polygons,'subject_overlap':[overlaps(footprint,p) for p in native_polygons],'participants':states},
      'drv.time_to_conflict':{'relative_kinematics':relative,'intersection_regions':native_polygons,'no_hazard_cutoff_selected':True},
      'drv.yields_to':{'subject_speed_mps':norm(v),'subject_native_lane':subject_lane,'participants':states,'relative_kinematics':relative,'legal_yield_conclusion': 'unresolved'},
      'drv.u_turn':{'heading_deg':t.rotation.yaw,'heading_change_from_initial_deg':(t.rotation.yaw-previous.setdefault('initial_yaw',t.rotation.yaw)+180)%360-180,'velocity_mps':xyz(v)},
      'st.curvature':{'native_yaw_deg':wp.transform.rotation.yaw if wp else t.rotation.yaw,'native_road':subject_lane,'sampling':'retained native route waypoints + road.xodr'},
      'st.grade':{'pitch_deg':wp.transform.rotation.pitch if wp else t.rotation.pitch,'native_road':subject_lane,'source':'actual native map waypoint pitch'},
      'rel.oncoming':relative,'drv.approaching':relative,'ru.truck':{'native_blueprints':[{'actor_id':p.id,'blueprint':p.type_id,'attributes':dict(p.attributes)} for p in participants],'goods_transport_context':a.get('goods_transport_class',{}).get('value',False)},
      'ru.trailer_or_combination':{'actual_blueprints':[{'actor_id':p.id,'blueprint':p.type_id} for p in participants],'trailer_inventory':[{'actor_id':p.id,'blueprint':p.type_id} for p in world.get_actors() if 'trailer' in p.type_id]},
      'drv.following':{'relative_kinematics':relative,'subject_lane':subject_lane},'rel.surface_gap':gap[0]['surface_gap_m'] if gap else {'other_actor_inventory':[]},'rel.ahead_behind_in_lane':{'relative_kinematics':relative,'subject_lane':subject_lane},'drv.laned_roadway':{'same_direction_lane_count':len(directions),'native_lanes':directions},'st.lane_adjacency':directions,'drv.overtaking':{'relative_kinematics':relative,'native_lane':subject_lane},
      'drv.backing':v.x*forward[0]+v.y*forward[1]<-.01,
      'st.intersection':{'native_polygons':native_polygons,'authored_polygon':a.get('intersection_polygon',{}).get('value',[])},
      'rel.occupies':{'native_intersection_overlap':[overlaps(footprint,p) for p in native_polygons],'native_crosswalk_overlap':[overlaps(footprint,p) for p in crosswalks],'authored_crosswalk_overlap':overlaps(footprint,a['crosswalk_polygon']['value']) if 'crosswalk_polygon' in a else False,'authored_intersection_overlap':overlaps(footprint,a['intersection_polygon']['value']) if a.get('intersection_polygon',{}).get('value') else False,'body_footprint':footprint,'contact_is_geometric':True,'legal_contact_convention_unresolved':True},
      'drv.turning':{'heading_deg':t.rotation.yaw,'angular_velocity_deg_s':ego.get_angular_velocity().z,'actual_reverse_signed_speed_mps':v.x*forward[0]+v.y*forward[1]}}
    if any(o['name']=='rel.visible' for o in c['observations']):record['rel.visible']=event['original_observations']['relations'] if event else [visible_relation(world,ego,p) for p in participants if p.id!=ego.id]
    if any(o['name']=='st.sight_distance' for o in c['observations']):
        from carla_sgg.law_evidence import actor_visibility
        record['st.sight_distance']=event['visibility'] if event else actor_visibility(world,ego,mapping=mapping)
        if not record['st.sight_distance']:raise RuntimeError('Required original visibility packet unavailable')
        approaches=record['st.sight_distance'].get('approaches',[])
        validate_visibility(record['st.sight_distance'],[-1,1] if c['mechanism']=='uturn' else None)
        projection=record['st.sight_distance']['ego_projection']
        for entry in approaches:
            native_lane=mapping.get_waypoint_xodr(projection['road_id'],entry['lane_id'],projection['s_m'])
            if native_lane is None or len(native_lane.previous(230.))!=1:raise RuntimeError('live_measurement: native lane route does not cover the full declared 230m search beyond first occlusion')
        if record['st.sight_distance'].get('unknown_reason') or not approaches or set(record['st.sight_distance'].get('required_lane_ids',[]))!={x['lane_id'] for x in approaches} or any(x.get('unknown_reason') or not x.get('any_body_sight_horizon') or x['any_body_sight_horizon'].get('unknown') or x['any_body_sight_horizon'].get('bound')=='route_limit' for x in approaches):raise RuntimeError('live_measurement: required every-frame nine-point visibility route coverage unavailable; retain attempt and rebuild native route')
        if c['mechanism']=='yield':
            # Independently retain both incoming cross-road approaches, without calling them ego incoming-lane horizons.
            from carla_sgg.law_evidence import sampled_horizon,ray_evidence
            targets=[t.transform(carla.Location(ego.bounding_box.location))]+list(ego.bounding_box.get_world_vertices(t));cross=[]
            for road in (3,4):
                def sample(distance):
                    station=490-distance if road==3 else distance
                    waypoint=mapping.get_waypoint_xodr(road,-1 if road==3 else 1,station)
                    if waypoint is None:return None
                    eye=waypoint.transform.location+carla.Location(z=1.4)
                    return [ray_evidence(world,ego,eye,p) for p in targets]
                horizon=sampled_horizon(sample,230.,10.,.25,checkpoints=[152.4])
                if sample(230.) is None:raise RuntimeError('live_measurement: cross incoming route ends before230m')
                if horizon.get('bound')=='route_limit' or horizon.get('unknown'):raise RuntimeError('live_measurement: cross-road incoming approach lacks complete 230m nine-body route coverage')
                cross.append({'road_id':road,'lane_id':-1 if road==3 else 1,'distance_origin':'native intersection approach endpoint; actor body targets remain actual original-frame positions','any_body_sight_horizon':horizon,'body_rays_at_152_4m':sample(152.4)})
            record['st.sight_distance']['through_road_incoming_approaches']=cross
    selected={o['name']:record[o['name']] for o in c['observations']}
    return selected,states,body
