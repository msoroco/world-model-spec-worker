"""Pinned Native lane readback requests for the 3(a) authored map."""
import hashlib

from geometry import open_drive

REQUESTS={
    'first_center_approach':(-40,0,1,-1,'Bidirectional'),
    'center_through_first_opportunity':(-9.5,0,14,-1,'Bidirectional'),
    'center_after_first_opportunity':(10,0,2,-1,'Bidirectional'),
    'later_through_lane':(35,3.5,2,-2,'Driving'),
    'first_left_exit':(-3,-20,4,-1,'Driving'),
    'later_left_exit':(47,-20,24,-1,'Driving')}


def survey(carla,mapping):
    observed={}
    for name,(x,y,road,lane,lane_type) in REQUESTS.items():
        requested=getattr(carla.LaneType,lane_type)
        waypoint=mapping.get_waypoint(carla.Location(x=x,y=y,z=.2),
                                      project_to_road=False,lane_type=requested)
        if waypoint is None or waypoint.road_id!=road or waypoint.lane_id!=lane:
            raise RuntimeError('Native lane readback failed: '+name)
        if waypoint.lane_type!=requested or abs(waypoint.lane_width-3.5)>.15:
            raise RuntimeError('Native lane type/width differs: '+name)
        expected=[1,0] if 'exit' not in name else [0,-1]
        forward=waypoint.transform.get_forward_vector()
        if forward.x*expected[0]+forward.y*expected[1]<.98:
            raise RuntimeError('Native direction differs: '+name)
        observed[name]={'road_id':road,'lane_id':lane,'lane_type':lane_type,
                        'lane_width_m':waypoint.lane_width,'native_center_xy_m':[x,y]}
    return {'authored_map_sha256':hashlib.sha256(open_drive().encode()).hexdigest(),
            'readback':observed,'native_lane_types_verified':True,
            'physical_turn_only_design_verified':False,
            'driver_purpose_verified':False}
