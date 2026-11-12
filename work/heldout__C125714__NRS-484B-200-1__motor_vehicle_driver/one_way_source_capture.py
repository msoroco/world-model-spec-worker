"""Retain original same-direction road, body and sign readback at 20 Hz."""

import json
from pathlib import Path

from one_way_construction import adjacent_same_direction_left, one_way_section


class OneWaySourceRecorder:
    def __init__(self, output, subject, sign):
        if subject.id==sign.id:
            raise ValueError('One-way sign and subject actor must differ')
        root=Path(output);root.mkdir(parents=True,exist_ok=True)
        self.road_path=root/'one_way_roadway.jsonl'
        self.sign_path=root/'one_way_sign.jsonl'
        self.road_file=self.road_path.open('x',encoding='utf-8')
        self.sign_file=self.sign_path.open('x',encoding='utf-8')
        self.subject,self.sign=subject,sign
        self.previous=None

    def append(self, frame, time_s, waypoint):
        if self.previous is not None and (
                frame!=self.previous[0]+1 or abs(time_s-self.previous[1]-.05)>1e-4):
            raise ValueError('One-way original source not continuous at 20 Hz')
        left=adjacent_same_direction_left(waypoint)
        road=one_way_section(waypoint,left)
        corners=self.subject.bounding_box.get_world_vertices(self.subject.get_transform())
        if len(corners)!=8:
            raise ValueError('One-way subject body box missing')
        bottom=sorted(corners,key=lambda p:p.z)[:4]
        road.update({'frame':int(frame),'time_s':float(time_s),
                     'ego_id':str(self.subject.id),
                     'ego_corners':[[float(p.x),float(p.y)] for p in bottom]})
        transform=self.sign.get_transform()
        point=transform.location
        sign={'frame':int(frame),'time_s':float(time_s),
              'actor_id':str(self.sign.id),'blueprint_id':self.sign.type_id,
              'position_m':[float(point.x),float(point.y),float(point.z)],
              'designation_verified':False,'posting_authority_verified':False}
        if 'oneway' not in sign['blueprint_id'].lower().replace('_',''):
            raise ValueError('One-way original sign actor changed type')
        self.road_file.write(json.dumps(road,sort_keys=True)+'\n');self.road_file.flush()
        self.sign_file.write(json.dumps(sign,sort_keys=True)+'\n');self.sign_file.flush()
        self.previous=(frame,time_s)
        return road,sign

    def close(self):
        self.road_file.close();self.sign_file.close()
