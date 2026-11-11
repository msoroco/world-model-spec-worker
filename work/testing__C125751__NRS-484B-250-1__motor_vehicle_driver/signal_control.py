"""Inventory the signal governing ego's Native entrance and check readback."""

def governing_signal(world, road_id, lane_id):
    lights=list(world.get_actors().filter('traffic.traffic_light*'))
    matches=[light for light in lights if any(wp.road_id==road_id and wp.lane_id==lane_id for wp in light.get_affected_lane_waypoints())]
    if len(matches)!=1:raise ValueError('Exactly one governing Native entrance signal required')
    light=matches[0]
    state=str(light.get_state()).split('.')[-1]
    if state not in ('Green','Yellow','Red','Off'):
        raise ValueError('Unrecognized governing signal state')
    return {'signal_actor_id':light.id,'road_id':road_id,'lane_id':lane_id,'native_state':state,
            'subsection_1_applicability':'subsection_4_qualification_required' if state=='Off' else 'excluded_by_official_device'}
