"""Native yield-sign crossing sources with four original camera frame identities."""
from contextlib import contextmanager
import json
import math

CAMERAS = {'overview': (1920,1080), 'approach': (1280,720),
           'reference_corner': (1280,720), 'driver_reference': (1280,720)}


@contextmanager
def source_cameras(world, ego, transforms):
    if set(transforms) != set(CAMERAS):
        raise ValueError('All four named source-camera transforms required')
    sensors=[]
    try:
        for name,(width,height) in CAMERAS.items():
            blueprint=world.get_blueprint_library().find('sensor.camera.rgb')
            if blueprint is None:
                raise ValueError('Native RGB camera blueprint missing')
            for key,value in (('image_size_x',width),('image_size_y',height),
                              ('fov',90),('sensor_tick',.05)):
                blueprint.set_attribute(key,str(value))
            kwargs={'attach_to':ego} if name=='driver_reference' else {}
            sensor=world.spawn_actor(blueprint,transforms[name],**kwargs)
            if sensor is None:
                raise ValueError('Native source-camera spawn failed: '+name)
            sensors.append((name,sensor))
        yield dict(sensors)
    finally:
        for _,sensor in reversed(sensors):
            sensor.stop();sensor.destroy()


def _finite(value,label):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite Native '+label+' required')
    return float(value)


def _body(actor,world_map,scene,role):
    pose=actor.get_transform()
    vertices=actor.bounding_box.get_world_vertices(pose)
    if len(vertices)<4:
        raise ValueError('Complete original Native body required')
    waypoint=world_map.get_waypoint(actor.get_location(),project_to_road=False)
    if waypoint is None:
        raise ValueError('Original Native waypoint missing')
    expected=scene['approaches'][role]
    if waypoint.road_id!=expected['road_id'] and not waypoint.is_junction:
        raise ValueError('Native approach road differs from scene')
    return {'actor_id':actor.id,'intersection_id':scene['intersection_id'],
            'road_id':expected['road_id'],
            'native_road_id':waypoint.road_id,'native_lane_id':waypoint.lane_id,
            'body_vertices_xy_m':[[_finite(v.x,'body x'),_finite(v.y,'body y')]
                                   for v in vertices],
            'position_xy_m':[_finite(pose.location.x,'x'),_finite(pose.location.y,'y')]}


def record_sample(frame_map,stream,snapshot,world_map,ego,other,sign,
                  camera_frames,scene,other_left_turn_intended=None):
    if set(camera_frames)!=set(CAMERAS) or any(
        camera_frames[name]!=snapshot.frame for name in CAMERAS):
        raise ValueError('All four camera frames must join the Native tick')
    if sign.id!=scene['yield_sign']['native_id']:
        raise ValueError('Governing Native yield sign changed')
    if scene['approach_relation']=='opposite_directions' and other_left_turn_intended is not True:
        raise ValueError('Original left-turn intention required')
    time_s=_finite(snapshot.timestamp.elapsed_seconds,'time')
    ego_row=_body(ego,world_map,scene,'ego')
    other_row=_body(other,world_map,scene,'other')
    if ego_row['actor_id']==other_row['actor_id']:
        raise ValueError('Distinct Native vehicle IDs required')
    mapped=frame_map.append(snapshot.frame,time_s)
    row={'frame':snapshot.frame,'time_s':time_s,
         'governing_yield_sign_id':sign.id,
         'other_left_turn_intended':other_left_turn_intended,
         'ego':ego_row,'other':other_row}
    stream.write(json.dumps(row,allow_nan=False)+'\n')
    return mapped,row
