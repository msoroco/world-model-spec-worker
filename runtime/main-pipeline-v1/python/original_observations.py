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
          'acceleration_mps2':xyz(acceleration),
          'accel_longitudinal_mps2':sum(a*b for a,b in zip(xyz(acceleration),xyz(forward))),
          'body_vertices_m':[xyz(p) for p in actor.bounding_box.get_world_vertices(transform)],
          'blueprint_attributes':dict(getattr(actor,'attributes',{})),
          'light_attributes':{}}
    if actor.type_id.startswith('vehicle.'):
        copy_carla_vehicle_lights(data['light_attributes'],actor)
    # The public API reports actual wheel angle on supported client versions.
    # Missing SDK/actor support remains unknown, never normalized steering.
    if hasattr(actor,'get_wheel_steer_angle'):
        try:
            import carla
            wheel=carla.VehicleWheelLocation.Front_Wheel if str(data['blueprint_attributes'].get('number_of_wheels'))=='2' else carla.VehicleWheelLocation.FL_Wheel
            data['wheel_steer_angle_deg']=actor.get_wheel_steer_angle(wheel)
            data['wheel_angle_reference']=str(wheel)+'; actual CARLA API degrees, not steering input'
        except (AttributeError,RuntimeError):pass
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


def device_state(actor):
    transform=actor.get_transform()
    record={'actor_id':actor.id,'blueprint':actor.type_id,'position_m':xyz(transform.location)}
    if hasattr(actor,'get_state'):record['state']=str(actor.get_state()).split('.')[-1]
    if hasattr(actor,'get_affected_lane_waypoints'):
        record['affected_lanes']=[[w.road_id,w.section_id,w.lane_id] for w in actor.get_affected_lane_waypoints()]
    if hasattr(actor,'get_opendrive_id'):
        value=actor.get_opendrive_id()
        if value:record['landmark_id']=str(value)
    return record


def observe(world, subject, frame, time_s, visibility=False, physical_registry=None):
    if world.get_snapshot().frame!=frame:raise RuntimeError('Observation frame mismatch')
    inventory=list(world.get_actors())
    actors=[a for a in inventory if a.type_id.startswith(('vehicle.','walker.'))]
    devices=[device_state(a) for a in inventory if a.type_id.startswith(('traffic.traffic_light','traffic.stop','traffic.speed_limit.'))]
    sensors=[{'actor_id':a.id,'blueprint':a.type_id,'position_m':xyz(a.get_transform().location),
              'rotation_deg':{axis:getattr(a.get_transform().rotation,axis)for axis in ('pitch','yaw','roll')},
              'attributes':dict(a.attributes),'parent_actor_id':getattr(getattr(a,'parent',None),'id',None)}
             for a in inventory if a.type_id.startswith('sensor.camera.rgb')]
    settings=world.get_settings()if hasattr(world,'get_settings')else None
    data={'rgb_sensors':sensors,'world_settings':{'no_rendering_mode':getattr(settings,'no_rendering_mode',None)},'frame':frame,'time_s':time_s,'devices':devices,'participants':[actor_state(a) for a in actors],
          'relations': [visible_relation(world,subject,a) for a in actors if a.id!=subject.id] if visibility else [],
          'participant_inventory':'all original live vehicle/walker actors; camera visibility independent'}
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
            known_devices[attrs['carla_id']]=node
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
        ident=device['actor_id'];name=known_devices.get(ident)
        if name is None and device.get('landmark_id'):
            candidates=[node for node,attrs in graph.nodes(data=True)if str(attrs.get('landmark_id'))==device['landmark_id']]
            if len(candidates)==1:name=candidates[0]
        if name is None:
            name='observed_device_%d'%ident
            graph.add_node(name,sem_class=device['blueprint'],carla_id=ident,entity_id=ident,
                vertex=np.array(device['position_m']),forward=np.array([1.,0.,0.]),
                right=np.array([0.,1.,0.]),up=np.array([0.,0.,1.]))
        attrs=graph.nodes[name]
        attrs['original_device_observation']=device
        if 'state' in device:attrs['light_state']=device['state']
        if 'landmark_id' in device:attrs['landmark_id']=device['landmark_id']
        if 'affected_lanes' in device:attrs['observed_governs']=device['affected_lanes']
    graph.graph['observed_evidence']=observation
    return graph
