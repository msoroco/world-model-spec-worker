"""Original Native marked approach, body, indicator and turn readbacks."""
import json
from math import atan2,hypot,isfinite
from pathlib import Path
from lane_sources import body_corners,marked_lane_slice

def xy(point):
    pair=[float(point.x),float(point.y)]
    if not all(map(isfinite,pair)):raise ValueError('Nonfinite Native position')
    return pair

def route_context(selection):
    start,end=selection['approach'][0],selection['exit']
    return {'format':'worker-marked-left-turn-route-context',
            'approach_road_id':selection['approach_road_id'],
            'approach_lane_id':selection['approach_lane_id'],
            'adjacent_lane_id':selection['adjacent_lane_id'],
            'exit_road_id':selection['exit_road_id'],
            'requested_heading_change_deg':selection['requested_heading_change_deg'],
            'approach_heading_xy':xy(start.transform.get_forward_vector()),
            'exit_heading_xy':xy(end.transform.get_forward_vector()),
            'connected_native_waypoints':True,'lawful_turn_facts':None,
            'legal_exception_claimed':False}

class TurnSourceRecorder:
    def __init__(self,directory,ego,selection):
        if ego.id is None:raise ValueError('Native ego id missing')
        self.ego,self.selection=ego,selection
        self.path=Path(directory)/'turn_originals.jsonl';self.stream=self.path.open('x',encoding='utf-8')
        self.previous=None
        (Path(directory)/'turn_scene_context.json').write_text(json.dumps(route_context(selection),indent=2)+'\n')
    def append(self,frame,time_s,current_waypoint):
        if type(frame) is not int or type(time_s) not in (float,int) or not isfinite(time_s):
            raise ValueError('Invalid Native turn frame')
        if self.previous and (frame!=self.previous[0]+1 or time_s<=self.previous[1]):
            raise ValueError('Turn original frames skipped')
        transform=self.ego.get_transform();position=xy(transform.location);heading=xy(transform.get_forward_vector())
        if hypot(*heading)<.1:raise ValueError('Native ego heading invalid')
        approach_active=(current_waypoint is not None and not current_waypoint.is_junction and
                         int(current_waypoint.road_id)==self.selection['approach_road_id'])
        lane=None
        if approach_active:
            anchor=min(self.selection['approach'],key=lambda wp:hypot(wp.transform.location.x-position[0],wp.transform.location.y-position[1]))
            lane=marked_lane_slice(anchor,half_length_m=5.)
        row={'frame':frame,'time_s':time_s,'ego_id':int(self.ego.id),
             'position_xy_m':position,'heading_xy':heading,
             'ego_corners_xy_m':body_corners(self.ego),
             'ego_velocity_xy_mps':xy(self.ego.get_velocity()),
             'ego_light_state':str(self.ego.get_light_state()) if hasattr(self.ego,'get_light_state') else None,
             'current_road_id':int(current_waypoint.road_id) if current_waypoint else None,
             'current_lane_id':int(current_waypoint.lane_id) if current_waypoint else None,
             'current_is_junction':bool(current_waypoint.is_junction) if current_waypoint else None,
             'approach_active':approach_active,'original_approach_lane':lane}
        self.stream.write(json.dumps(row,allow_nan=False)+'\n');self.stream.flush();self.previous=(frame,time_s)
        return row
    def close(self):self.stream.close()
