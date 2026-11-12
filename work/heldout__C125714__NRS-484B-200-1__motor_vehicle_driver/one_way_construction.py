"""Construct a same-direction two-lane roadway with a visible one-way sign actor.

Lane topology and a sign actor are physical candidates. They do not establish
official road designation or sign authority.
"""

from math import hypot


def _unit(waypoint):
    vector=waypoint.transform.get_forward_vector()
    length=hypot(vector.x,vector.y)
    if length<.8:
        raise ValueError('One-way lane tangent unavailable')
    return vector.x/length,vector.y/length


def adjacent_same_direction_left(right_lane):
    left=right_lane.get_left_lane()
    if left is None or left.road_id!=right_lane.road_id:
        raise ValueError('One-way left traffic lane missing')
    if left.lane_width<=0 or right_lane.lane_width<=0 or left.lane_id==right_lane.lane_id:
        raise ValueError('One-way mapped lane widths or identities invalid')
    rx,ry=_unit(right_lane);lx,ly=_unit(left)
    if rx*lx+ry*ly<.95:
        raise ValueError('One-way adjacent lane travels another direction')
    right=(-ry,rx)
    a=right_lane.transform.location;b=left.transform.location
    lateral=(b.x-a.x)*right[0]+(b.y-a.y)*right[1]
    if abs(lateral+(right_lane.lane_width+left.lane_width)/2)>.4:
        raise ValueError('One-way lanes are not joined')
    if right_lane.get_right_lane() is not None or left.get_left_lane() is not None:
        raise ValueError('One-way construction requires two bounded traffic lanes')
    return left


def select_one_way_route(world_map, *, direction='east', minimum_steps=12, step_m=2.5):
    if direction not in ('east','west'):
        raise ValueError('One-way direction unsupported')
    for spawn in world_map.get_spawn_points():
        start=world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        tx,_=_unit(start)
        if (direction=='east' and tx<=.8) or (direction=='west' and tx>=-.8):
            continue
        try:
            adjacent_same_direction_left(start)
        except ValueError:
            continue
        route=[start]
        for _ in range(minimum_steps):
            options=[w for w in route[-1].next(step_m)
                     if w.road_id==start.road_id and w.lane_id==start.lane_id and
                        not w.is_junction]
            if not options:
                break
            try:
                adjacent_same_direction_left(options[0])
            except ValueError:
                break
            route.append(options[0])
        if len(route)==minimum_steps+1:
            return route
    raise ValueError('No connected bounded same-direction two-lane route')


def one_way_section(right_lane,left_lane):
    selected=adjacent_same_direction_left(right_lane)
    if (selected.road_id,selected.lane_id)!=(left_lane.road_id,left_lane.lane_id):
        raise ValueError('One-way original lane pair differs')
    tx,ty=_unit(right_lane);lx,ly=_unit(left_lane);right=(-ty,tx)
    a=right_lane.transform.location;b=left_lane.transform.location
    right_edge=[a.x+right[0]*right_lane.lane_width/2,
                a.y+right[1]*right_lane.lane_width/2]
    left_edge=[b.x-right[0]*left_lane.lane_width/2,
               b.y-right[1]*left_lane.lane_width/2]
    center=[(right_edge[i]+left_edge[i])/2 for i in (0,1)]
    return {'roadway_center_point_xy':center,'travel_tangent_xy':[tx,ty],
            'left_lane_tangent_xy':[lx,ly],
            'left_road_edge_xy':left_edge,'right_road_edge_xy':right_edge,
            'right_lane_id':right_lane.lane_id,'left_lane_id':left_lane.lane_id,
            'road_id':right_lane.road_id,'right_lane_width_m':float(right_lane.lane_width),
            'left_lane_width_m':float(left_lane.lane_width)}


def spawn_one_way_sign(world, carla, waypoint):
    library=world.get_blueprint_library()
    blueprints=list(library.filter('*oneway*'))+list(library.filter('*one_way*'))
    unique={bp.id:bp for bp in blueprints}
    if not unique:
        raise ValueError('Native one-way sign blueprint unavailable')
    blueprint=unique[sorted(unique)[0]]
    tx,ty=_unit(waypoint);right=(-ty,tx)
    source=waypoint.transform.location
    transform=carla.Transform(carla.Location(
        x=source.x+tx*5+right[0]*(waypoint.lane_width/2+.5),
        y=source.y+ty*5+right[1]*(waypoint.lane_width/2+.5),
        z=source.z+.1),waypoint.transform.rotation)
    actor=world.try_spawn_actor(blueprint,transform)
    if actor is None:
        raise ValueError('Native one-way sign spawn failed')
    return actor
