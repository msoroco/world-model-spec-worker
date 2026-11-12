"""Select and read back an engineered three-traffic-lane Native road section."""

from math import hypot


def _unit(waypoint):
    vector=waypoint.transform.get_forward_vector();norm=hypot(vector.x,vector.y)
    if norm<.8:raise ValueError('Three-lane tangent unavailable')
    return vector.x/norm,vector.y/norm


def three_lane_neighbors(right_lane):
    center=right_lane.get_left_lane()
    far_left=center.get_left_lane() if center is not None else None
    if center is None or far_left is None or any(
            lane.road_id!=right_lane.road_id or lane.lane_width<=0
            for lane in (right_lane,center,far_left)):
        raise ValueError('Three traffic lanes on one mapped road required')
    if len({right_lane.lane_id,center.lane_id,far_left.lane_id})!=3:
        raise ValueError('Three-lane mapped lane identities differ')
    a=_unit(right_lane);b=_unit(center);c=_unit(far_left)
    if sum(a[i]*b[i] for i in (0,1))<.95 or sum(a[i]*c[i] for i in (0,1))>-.95:
        raise ValueError('Three-lane direction pattern differs')
    right=(-a[1],a[0])
    for first,second in ((right_lane,center),(center,far_left)):
        p=first.transform.location;q=second.transform.location
        separation=(q.x-p.x)*right[0]+(q.y-p.y)*right[1]
        if abs(separation+(first.lane_width+second.lane_width)/2)>.4:
            raise ValueError('Three-lane traffic lanes are not joined')
    if right_lane.get_right_lane() is not None or far_left.get_left_lane() is not None:
        raise ValueError('Three-lane section has additional traffic lanes')
    return center,far_left


def select_three_lane_route(world_map,*,direction='east',minimum_steps=12,step_m=2.5):
    if direction not in ('east','west'):
        raise ValueError('Three-lane route direction unsupported')
    for spawn in world_map.get_spawn_points():
        start=world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:continue
        tx,_=_unit(start)
        if (direction=='east' and tx<=.8) or (direction=='west' and tx>=-.8):continue
        try:three_lane_neighbors(start)
        except ValueError:continue
        route=[start]
        for _ in range(minimum_steps):
            options=[w for w in route[-1].next(step_m)
                     if w.road_id==start.road_id and w.lane_id==start.lane_id and not w.is_junction]
            if not options:break
            try:three_lane_neighbors(options[0])
            except ValueError:break
            route.append(options[0])
        if len(route)==minimum_steps+1:return route
    raise ValueError('No connected three-lane route with selected direction pattern')


def three_lane_section(right_lane):
    center,far_left=three_lane_neighbors(right_lane)
    tangent=_unit(right_lane);center_tangent=_unit(center);far_tangent=_unit(far_left)
    right=(-tangent[1],tangent[0])
    a=right_lane.transform.location;b=far_left.transform.location
    right_edge=[a.x+right[0]*right_lane.lane_width/2,
                a.y+right[1]*right_lane.lane_width/2]
    left_edge=[b.x-right[0]*far_left.lane_width/2,
               b.y-right[1]*far_left.lane_width/2]
    centerline=[(right_edge[i]+left_edge[i])/2 for i in (0,1)]
    return {'roadway_center_point_xy':centerline,'travel_tangent_xy':list(tangent),
            'center_lane_tangent_xy':list(center_tangent),
            'far_left_lane_tangent_xy':list(far_tangent),
            'left_road_edge_xy':left_edge,'right_road_edge_xy':right_edge,
            'road_id':right_lane.road_id,
            'right_lane_id':right_lane.lane_id,'center_lane_id':center.lane_id,
            'far_left_lane_id':far_left.lane_id,
            'lane_widths_m':[float(x.lane_width) for x in (right_lane,center,far_left)],
            'applicable_lane_rule_verified':False}
