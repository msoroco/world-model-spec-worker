"""Retain original three-lane map and full subject body rows at 20 Hz."""

import json
from pathlib import Path

from three_lane_construction import three_lane_section


class ThreeLaneSourceRecorder:
    def __init__(self,output,subject):
        self.subject=subject
        self.path=Path(output)/'three_lane_roadway.jsonl'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('x',encoding='utf-8')
        self.previous=None

    def append(self,frame,time_s,waypoint):
        if self.previous is not None and (
                frame!=self.previous[0]+1 or abs(time_s-self.previous[1]-.05)>1e-4):
            raise ValueError('Three-lane original source not continuous at 20 Hz')
        row=three_lane_section(waypoint)
        vertices=self.subject.bounding_box.get_world_vertices(self.subject.get_transform())
        if len(vertices)!=8:
            raise ValueError('Three-lane subject body box missing')
        bottom=sorted(vertices,key=lambda p:p.z)[:4]
        row.update({'frame':int(frame),'time_s':float(time_s),'ego_id':str(self.subject.id),
                    'ego_corners':[[float(p.x),float(p.y)] for p in bottom]})
        self.file.write(json.dumps(row,sort_keys=True)+'\n');self.file.flush()
        self.previous=(frame,time_s)
        return row

    def close(self):
        self.file.close()
