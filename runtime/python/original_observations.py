"""Original same-frame actor observations; no controller targets or tick ownership."""
import math


def xyz(value):
    return [value.x,value.y,value.z]


def actor_state(actor):
    from carla_sgg.sgg import copy_carla_vehicle_lights
    transform=actor.get_transform();velocity=actor.get_velocity();acceleration=actor.get_acceleration()
    forward=transform.get_forward_vector()
    data={'actor_id':actor.id,'blueprint':actor.type_id,'position_m':xyz(transform.location),
          'heading_deg':transform.rotation.yaw,'velocity_mps':xyz(velocity),
          'speed_mps':math.sqrt(sum(v*v for v in xyz(velocity))),
          'acceleration_mps2':xyz(acceleration),'forward_vector':xyz(forward),
          'body_vertices_m':[xyz(p) for p in actor.bounding_box.get_world_vertices(transform)],
          'blueprint_attributes':dict(getattr(actor,'attributes',{})),
          'light_attributes':{}}
    from traffic_spec_adapter.acceleration import horizontal_acceleration, METHOD
    value, projection = horizontal_acceleration(data)
    data['acceleration_method'] = METHOD
    data['acceleration_projection'] = projection
    if value is not None:data['accel_longitudinal_mps2'] = value
    if actor.type_id.startswith('vehicle.'):
        copy_carla_vehicle_lights(data['light_attributes'],actor)
    if actor.type_id.startswith('vehicle.'):
        try:
            control = actor.get_control()
            data['applied_control'] = {key: getattr(control, key) for key in
                ('throttle', 'brake', 'hand_brake')}
        except (AttributeError, RuntimeError) as exc:
            data['control_error'] = str(exc)
        wheels = str(data['blueprint_attributes'].get('number_of_wheels'))
        references = ({'front': 'Front_Wheel'} if wheels == '2' else
                      {'front_left': 'FL_Wheel', 'front_right': 'FR_Wheel'} if wheels == '4' else {})
        data['wheel_angle_method'] = 'single_front_v1' if wheels == '2' else 'front_wheel_mean_v1' if wheels == '4' else None
        data['wheel_angle_references'] = references
        data['wheel_steer_angles_deg'] = {}
        data['wheel_angle_errors'] = {}
        if not references:
            data['wheel_angle_errors']['layout'] = 'unsupported or unverified wheel layout'
        for key, name in references.items():
            try:
                import carla
                value = actor.get_wheel_steer_angle(getattr(carla.VehicleWheelLocation, name))
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('nonfinite or nonnumeric wheel angle')
                data['wheel_steer_angles_deg'][key] = value
            except (AttributeError, RuntimeError, ValueError) as exc:
                data['wheel_angle_errors'][key] = str(exc)
    return data


def visible_relation(world, observer, target):
    """Any-body collision LOS, retaining every hit and excluding both actor bodies.

    Subject reference: local (0,0,1.5)m. This collision-mesh estimate is not human
    recognizability, atmospheric visibility, or roadway sight distance.
    """
    import carla
    eye=observer.get_transform().transform(carla.Location(z=1.5))
    transform=target.get_transform()
    vertices=list(target.bounding_box.get_world_vertices(transform))
    centre=carla.Location(x=sum(v.x for v in vertices)/len(vertices),
                          y=sum(v.y for v in vertices)/len(vertices),z=sum(v.z for v in vertices)/len(vertices))
    rays=[]
    for endpoint in vertices+[centre]:
        blockers=[]
        for hit in world.cast_ray(eye,endpoint):
            if observer.bounding_box.contains(hit.location,observer.get_transform()):continue
            if target.bounding_box.contains(hit.location,transform):continue
            if hit.location.distance(eye)<.05 or hit.location.distance(endpoint)<.02:continue
            blockers.append({'label':str(hit.label),'location_m':xyz(hit.location)})
        rays.append({'observer_m':xyz(eye),'target_m':xyz(endpoint),'blockers':blockers,'clear':not blockers})
    return {'a':observer.id,'b':target.id,'visible':any(r['clear'] for r in rays),
            'method':'any_of_nine_body_collision_rays_subject_reference_z_1.5m','rays':rays}


def native_vector(value):
    values=xyz(value)
    if any(not isinstance(v,(int,float))or isinstance(v,bool)or not math.isfinite(v)for v in values):
        raise ValueError('Nonfinite or invalid native geometry vector')
    return values


def native_rotation(value):
    values={axis:getattr(value,axis)for axis in ('pitch','yaw','roll')}
    if any(not isinstance(v,(int,float))or isinstance(v,bool)or not math.isfinite(v)for v in values.values()):
        raise ValueError('Nonfinite or invalid native geometry rotation')
    return values


def native_box(box):
    """Retain the native API bounds; do not infer covering or emitted light."""
    return {'location_m':native_vector(box.location),'extent_m':native_vector(box.extent),
            'rotation_deg':native_rotation(box.rotation),
            'vertices_m':[native_vector(point)for point in box.get_local_vertices()],
            'vertices_api':'BoundingBox.get_local_vertices'}


def landmark_lane_validity(entry):
    """Preserve SDK native validity endpoints; no affected-lane inference."""
    if isinstance(entry, (tuple, list)):
        if len(entry) != 2:
            raise ValueError('Native lane validity needs exactly two endpoints')
        first, last = entry
    else:
        first, last = entry.from_lane, entry.to_lane
    if type(first) is not int or type(last) is not int:
        raise ValueError('Native lane validity endpoints must be integers')
    return {'from_lane': first, 'to_lane': last}


def map_control_inventory(world):
    """Raw native/map control evidence at initialization, not physical absence."""
    result={'scope':'capture_initialization','physical_absence_verified':False,
            'environment_queries':{},'landmarks':[],'errors':{},
            'limitation':'Native semantic inventories do not establish rendered absence, enabled state, covering or legal device class.'}
    if hasattr(world,'get_environment_objects'):
        import carla
        for name in ('TrafficSigns','TrafficLight'):
            try:
                label=getattr(carla.CityObjectLabel,name)
                entries=[]
                for obj in world.get_environment_objects(label):
                    entry={'native_id':int(obj.id),'native_name':obj.name,'enabled':None,'observation_errors':{}}
                    try:
                        transform=obj.transform
                        entry.update(position_m=native_vector(transform.location),
                            rotation_deg=native_rotation(transform.rotation),
                            bounds=native_box(obj.bounding_box))
                    except (AttributeError,RuntimeError,ValueError)as exc:entry['observation_errors']['geometry']=str(exc)
                    entries.append(entry)
                result['environment_queries'][name]={'objects':entries,'query_complete':True}
            except (AttributeError,RuntimeError,ValueError)as exc:
                result['environment_queries'][name]={'query_complete':False,'error':str(exc)}
    else:result['errors']['environment_objects']='World.get_environment_objects unavailable'
    try:
        for landmark in world.get_map().get_all_landmarks():
            record={key:str(getattr(landmark,key))for key in ('id','type','sub_type','unit','orientation')}
            record.update({key:getattr(landmark,key)for key in ('road_id','s','t','value','is_dynamic')})
            record['position_m']=xyz(landmark.transform.location)
            record['lane_validities']=[landmark_lane_validity(entry)for entry in landmark.get_lane_validities()]
            result['landmarks'].append(record)
        result['landmark_query_complete']=True
    except (AttributeError,RuntimeError,ValueError)as exc:
        result['landmark_query_complete']=False;result['errors']['landmarks']=str(exc)
    return result


def device_state(actor):
    record={'actor_id':actor.id,'blueprint':actor.type_id,'observation_errors':{}}
    errors=record['observation_errors']
    try:
        transform=actor.get_transform();record['position_m']=native_vector(transform.location)
        if hasattr(transform,'rotation'):
            record['rotation_deg']=native_rotation(transform.rotation)
    except (AttributeError,RuntimeError,ValueError)as exc:errors['transform']=str(exc);transform=None
    if actor.type_id.startswith('traffic.traffic_light'):
        try:record['state']=str(actor.get_state()).split('.')[-1]
        except (AttributeError,RuntimeError)as exc:errors['state']=str(exc)
        try:
            record['light_boxes']=[]
            for index,box in enumerate(actor.get_light_boxes()):
                head={'light_box_index':index}
                try:head.update(native_box(box))
                except (AttributeError,RuntimeError,ValueError)as exc:head['geometry_error']=str(exc)
                record['light_boxes'].append(head)
            record['light_box_method']='TrafficLight.get_light_boxes'
        except (AttributeError,RuntimeError,ValueError)as exc:errors['light_boxes']=str(exc)
        try:
            record['stop_waypoints']=[{'road_id':w.road_id,'section_id':w.section_id,
                'lane_id':w.lane_id,'s_m':w.s,'position_m':xyz(w.transform.location),
                'junction_id':w.junction_id if w.is_junction else None}
                for w in actor.get_stop_waypoints()]
        except (AttributeError,RuntimeError)as exc:errors['stop_waypoints']=str(exc)
    if hasattr(actor,'get_affected_lane_waypoints'):
        try:record['affected_lanes']=[[w.road_id,w.section_id,w.lane_id]for w in actor.get_affected_lane_waypoints()]
        except (AttributeError,RuntimeError)as exc:errors['affected_lanes']=str(exc)
    if actor.type_id.startswith('traffic.stop'):
        try:
            if transform is None:raise ValueError('Original sign transform unavailable')
            record['trigger_vertices_m']=[xyz(v)for v in actor.trigger_volume.get_world_vertices(transform)]
        except (AttributeError,RuntimeError,ValueError)as exc:errors['trigger_volume']=str(exc)
    if hasattr(actor,'get_opendrive_id'):
        try:
            value=actor.get_opendrive_id()
            if value:record['landmark_id']=str(value)
        except (AttributeError,RuntimeError)as exc:errors['landmark_id']=str(exc)
    return record


def observe(world, subject, frame, time_s, visibility=False, physical_registry=None):
    if world.get_snapshot().frame!=frame:raise RuntimeError('Observation frame mismatch')
    inventory=list(world.get_actors())
    actors=[a for a in inventory if a.type_id.startswith(('vehicle.','walker.'))]
    devices=[device_state(a) for a in inventory if a.type_id.startswith('traffic.')]
    sensors=[{'actor_id':a.id,'blueprint':a.type_id,'position_m':xyz(a.get_transform().location),
              'rotation_deg':{axis:getattr(a.get_transform().rotation,axis)for axis in ('pitch','yaw','roll')},
              'attributes':dict(a.attributes),'parent_actor_id':getattr(getattr(a,'parent',None),'id',None)}
             for a in inventory if a.type_id.startswith('sensor.camera.rgb')]
    settings=world.get_settings()if hasattr(world,'get_settings')else None
    data={'world_actor_inventory':world_actor_inventory(inventory,frame,time_s),'rgb_sensors':sensors,'world_settings':{'no_rendering_mode':getattr(settings,'no_rendering_mode',None)},'frame':frame,'time_s':time_s,'devices':devices,'participants':[actor_state(a) for a in actors],
          'relations': [visible_relation(world,subject,a) for a in actors if a.id!=subject.id] if visibility else [],
          'participant_inventory':'all original live vehicle/walker actors; camera visibility independent',
          'control_inventory':'all original live traffic.* actors; stop waypoints and trigger geometry queried in this frame; errors retained; no physical absence claim',
          'control_actor_ids':[device['actor_id']for device in devices],
          'control_actor_inventory':{'method':'World.get_actors','prefix':'traffic.',
              'complete':True,'frame':frame,'time_s':time_s,
              'actor_ids':[device['actor_id']for device in devices]}}
    if world.get_snapshot().frame!=frame:raise RuntimeError('World advanced during original observations')
    if physical_registry:
        from traffic_spec_adapter.physical_actors import observe_actor,validate_frame
        data['participants'].extend(observe_actor(a,physical_registry,actor_state) for a in inventory if a.id in physical_registry['actors'])
        validate_frame(data['participants'],physical_registry)
        data['participant_inventory']+='; source-verified registered generic animal actors'
    return data


def merge_graph(graph, observation):
    """Merge by recorded CARLA ID; supplement out-of-crop users once, not aliases."""
    import numpy as np
    from shapely.geometry import MultiPoint
    known_users={};known_devices={}
    generic_ids={a['actor_id'] for a in observation['participants'] if a.get('physical_classification')}
    for node,attrs in graph.nodes(data=True):
        kind=attrs.get('carla_type_id',attrs.get('sem_class',''))
        if not isinstance(kind,str):kind=''
        if kind=='ego' or kind.startswith(('vehicle.','walker.')) or attrs.get('carla_id',attrs.get('entity_id')) in generic_ids:
            known_users[attrs.get('carla_id',attrs.get('entity_id'))]=node
        elif kind.startswith('traffic.') and attrs.get('carla_id')is not None:
            known_devices.setdefault(attrs['carla_id'],[]).append(node)
    for actor in observation['participants']:
        ident=actor['actor_id']
        name=known_users.get(ident)
        if name is None:
            name='observed_actor_%d'%ident
            angle=math.radians(actor['heading_deg']);vertices=np.array(actor['body_vertices_m'])
            position=np.array(actor['position_m']);forward=np.array([math.cos(angle),math.sin(angle),0.])
            graph.add_node(name,sem_class=actor['blueprint'],carla_id=ident,entity_id=ident,
                vertex=position,forward=forward,right=np.array([-forward[1],forward[0],0.]),up=np.array([0.,0.,1.]),
                threedbbox=vertices)
            graph.graph.setdefault('bbox',{})[name]=MultiPoint(vertices[:,:2]).convex_hull
        attrs=graph.nodes[name]
        if actor.get('physical_classification'):
            attrs['native_actor_forward_before_body_axis_projection']=attrs.get('forward')
            angle=math.radians(actor['heading_deg']);attrs['forward']=np.array([math.cos(angle),math.sin(angle),0.]);attrs['threedbbox']=np.array(actor['body_vertices_m']);attrs['physical_classification']=actor['physical_classification']
        attrs['original_observation']=actor
        attrs.update(actor['light_attributes'])
        attrs['carla_speed']=actor['speed_mps']
        for axis,value in zip('xyz',actor['velocity_mps']):attrs['carla_vel_'+axis]=value
        for axis,value in zip('xyz',actor['acceleration_mps2']):attrs['carla_acc_'+axis]=value
    for device in observation.get('devices',[]):
        ident=device['actor_id'];names=known_devices.get(ident,[])
        boxes=device.get('light_boxes')
        if device['blueprint']=='traffic.traffic_light' and isinstance(boxes,list) and boxes:
            indexed={}
            for node in names:
                index=graph.nodes[node].get('carla_light_box_index')
                if index is None:continue
                if index in indexed:raise ValueError('Duplicate native light-box identity for actor '+str(ident))
                indexed[index]=node
            # A legacy actor-level proxy is not an additional physical head.
            for node in names:
                if graph.nodes[node].get('carla_light_box_index')is None:graph.remove_node(node)
            names=[];seen=set()
            for box in boxes:
                index=box.get('light_box_index')
                if type(index)is not int or index<0 or index in seen:raise ValueError('Invalid native light-box group index')
                seen.add(index);name=indexed.get(index);position=box.get('location_m')
                if name is None:
                    if position is None:continue  # Raw scope retains the unresolved group; export must reject incomplete projection.
                    name='observed_signal_group_%d_%d'%(ident,index)
                    graph.add_node(name,sem_class=device['blueprint'],carla_id=ident,entity_id=ident,
                        carla_light_box_index=index,signal_group_source='TrafficLight.get_light_boxes',
                        vertex=np.array(position),forward=np.array([1.,0.,0.]),
                        right=np.array([0.,1.,0.]),up=np.array([0.,0.,1.]))
                    vertices=box.get('vertices_m')
                    if vertices:graph.graph.setdefault('bbox',{})[name]=MultiPoint([point[:2]for point in vertices]).convex_hull
                elif position is not None and any(abs(float(a)-b)>1e-4 for a,b in zip(graph.nodes[name]['vertex'],position)):
                    raise ValueError('Same-frame native light-box index/geometry conflict for actor '+str(ident))
                graph.nodes[name]['original_signal_group']=box
                names.append(name)
        else:
            if not names and device.get('landmark_id'):
                candidates=[node for node,attrs in graph.nodes(data=True)if str(attrs.get('landmark_id'))==device['landmark_id']]
                if len(candidates)==1:names=candidates
            if not names:
                name='observed_device_%d'%ident
                graph.add_node(name,sem_class=device['blueprint'],carla_id=ident,entity_id=ident,
                    vertex=np.array(device['position_m']),forward=np.array([1.,0.,0.]),
                    right=np.array([0.,1.,0.]),up=np.array([0.,0.,1.]))
                names=[name]
        for name in names:
            attrs=graph.nodes[name]
            attrs['original_device_observation']=device
            if 'state' in device:attrs['light_state']=device['state']
            elif 'state' in device.get('observation_errors',{}):attrs.pop('light_state',None)
            if 'landmark_id' in device:attrs['landmark_id']=device['landmark_id']
            if 'affected_lanes' in device:attrs['observed_governs']=device['affected_lanes']
            elif 'affected_lanes' in device.get('observation_errors',{}):attrs.pop('observed_governs',None)
    graph.graph['observed_evidence']=observation
    return graph


def map_lane_topology(mapping, source_path):
    """Read back each source driving-lane section; never infer rendered inventory."""
    import hashlib
    import xml.etree.ElementTree as ET
    from pathlib import Path
    source=Path(source_path);root=ET.fromstring(source.read_bytes())
    result={'schema':'native-lane-section-readback-v1',
            'map_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'api':'Map.get_waypoint_xodr','lanes':[],'errors':[],
            'scope':'source driving-lane section identities and junction membership only'}
    for road in root.findall('road'):
        sections=road.findall('./lanes/laneSection')
        for index,section in enumerate(sections):
            start=float(section.get('s'));end=float(sections[index+1].get('s'))if index+1<len(sections)else float(road.get('length'))
            for lane in section.findall('./left/lane')+section.findall('./right/lane'):
                if lane.get('type')!='driving':continue
                identity=[int(road.get('id')),index,int(lane.get('id'))]
                samples=[]
                try:
                    if not end>start:raise ValueError('Nonpositive source lane interval')
                    margin=min(1e-4,(end-start)/4)
                    for station in sorted({start+margin,(start+end)/2,end-margin}):
                        waypoint=mapping.get_waypoint_xodr(identity[0],identity[2],station)
                        if waypoint is None:raise ValueError('Native waypoint unavailable')
                        observed=[waypoint.road_id,waypoint.section_id,waypoint.lane_id]
                        junction=int(road.get('junction','-1'))
                        if observed!=identity or bool(waypoint.is_junction)!=(junction>=0) or (junction>=0 and waypoint.junction_id!=junction):
                            raise ValueError('Native lane identity or junction differs from source')
                        samples.append({'s_m':station,'native_identity':observed,
                            'is_junction':bool(waypoint.is_junction),
                            'junction_id':waypoint.junction_id if waypoint.is_junction else None})
                    result['lanes'].append({'identity':identity,'station_interval_m':[start,end],'samples':samples})
                except (AttributeError,RuntimeError,ValueError)as exc:
                    result['errors'].append({'identity':identity,'error':str(exc)})
    result['complete']=bool(result['lanes'])and not result['errors']
    return result


def client_versions(client):
    """Record queried runtime versions; missing SDK methods remain explicit gaps."""
    result={'errors':{}}
    for name,method in (('client_version','get_client_version'),('server_version','get_server_version')):
        try:
            value=getattr(client,method)()
            if not isinstance(value,str)or not value:raise ValueError('Version response is not a nonempty string')
            result[name]=value
        except (AttributeError,RuntimeError,ValueError)as error:result['errors'][name]=str(error)
    return result


def world_actor_inventory(actors,frame,time_s):
    """Retain all API actor identities, including generic mesh attributes.

    This enumerates actors, not every static/baked rendered object. It cannot
    alone establish an absent sign, an unrestricted legend or official authority.
    """
    records=[]
    for actor in actors:
        record={'actor_id':actor.id,'blueprint':actor.type_id,'errors':{}}
        try:record['attributes']=dict(actor.attributes)
        except (AttributeError,RuntimeError,ValueError)as error:record['errors']['attributes']=str(error)
        try:record['parent_actor_id']=getattr(getattr(actor,'parent',None),'id',None)
        except (AttributeError,RuntimeError)as error:record['errors']['parent_actor_id']=str(error)
        records.append(record)
    return {'method':'World.get_actors','frame':frame,'time_s':time_s,'complete':True,
            'scope':'complete API actor query; static baked meshes are outside this inventory',
            'actors':records}
