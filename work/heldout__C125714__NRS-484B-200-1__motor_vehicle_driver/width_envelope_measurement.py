"""Measure original road and body widths without deciding statutory sufficiency."""

import json
from math import hypot, isfinite
from pathlib import Path


def measure_width(path):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Original width rows missing')
    output=[]
    ego_id=None
    for index,row in enumerate(rows):
        if ego_id is None:
            ego_id=row.get('ego_id')
        if not ego_id or row.get('ego_id')!=ego_id:
            raise ValueError('Original width subject changed')
        if index and (row['frame']!=rows[index-1]['frame']+1 or
                      abs(row['time_s']-rows[index-1]['time_s']-.05)>1e-4):
            raise ValueError('Original width rows not continuous at 20 Hz')
        tangent=row['travel_tangent_xy']
        norm=hypot(*tangent)
        if not .99<=norm<=1.01:
            raise ValueError('Original width tangent invalid')
        right=(-tangent[1]/norm,tangent[0]/norm)
        left_edge=row['left_road_edge_xy'];right_edge=row['right_road_edge_xy']
        width=sum((right_edge[i]-left_edge[i])*right[i] for i in (0,1))
        corners=row['ego_corners']
        if len(corners)!=4:
            raise ValueError('Original width needs four body corners')
        lateral=[sum(point[i]*right[i] for i in (0,1)) for point in corners]
        body_width=max(lateral)-min(lateral)
        half_width=float(row['subject_lane_width_m'])
        opposite_width=float(row['opposite_lane_width_m'])
        if (not all(isfinite(v) and v>0 for v in (width,body_width,half_width,opposite_width)) or
                abs(width-half_width-opposite_width)>.05):
            raise ValueError('Original roadway and body width geometry inconsistent')
        output.append({'frame':row['frame'],'time_s':row['time_s'],
                       'roadway_width_m':width,'right_half_width_m':half_width,
                       'body_lateral_width_m':body_width,
                       'right_half_clearance_m':half_width-body_width})
    return {'observations':output,
            'minimum_roadway_width_m':min(row['roadway_width_m'] for row in output),
            'minimum_right_half_clearance_m':min(row['right_half_clearance_m'] for row in output),
            'legal_sufficiency_decided':False}
