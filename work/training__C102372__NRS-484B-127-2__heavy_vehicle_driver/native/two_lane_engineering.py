"""Four planned Native constructions for the same-cell two-lane exception."""
from __future__ import annotations
import hashlib
import json
import xml.etree.ElementTree as ET
from engineering import CANDIDATES,parameters
from two_lane_exception import two_lane_open_drive

CASE='two_lane_exception'
ASSIGNMENT='training__C102372__NRS-484B-127-2__heavy_vehicle_driver'


def construction(candidate):
    if candidate not in CANDIDATES:raise ValueError('Unknown two-lane candidate')
    base=parameters('probe_2',candidate)
    return {**base,'case':CASE,'case_id':ASSIGNMENT+'__'+CASE,
            'comparison_variable':'same_direction_lane_count',
            'same_direction_lane_count':2,
            'road_variant':'two_same_direction_lanes',
            'authored_road_sha256':hashlib.sha256(two_lane_open_drive().encode()).hexdigest(),
            'status':'planned_native_construction',
            'physical_lane_availability_verified':False}


def check():
    root=ET.fromstring(two_lane_open_drive())
    lanes=root.findall('road/lanes/laneSection/right/lane')
    if [(int(lane.get('id')),float(lane.find('width').get('a'))) for lane in lanes]!=[(-1,4.),(-2,4.)]:
        raise ValueError('Authored two-lane Native road differs')
    variants={candidate:construction(candidate) for candidate in CANDIDATES}
    fixed=('case','case_id','target_gap_m','law_id','cell_id','actor','comparison_variable',
           'same_direction_lane_count','road_variant','authored_road_sha256')
    if any(any(value[key]!=variants['primary'][key] for key in fixed) for value in variants.values()):
        raise ValueError('Two-lane candidate changes statutory mechanism')
    if any(value['knobs']['rate_hz']!=20 or value['knobs']['duration_s']!=24 or
           value['target_gap_m']!=140 for value in variants.values()):
        raise ValueError('Two-lane candidate timing or gap differs')
    hashes={candidate:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            for candidate,value in variants.items()}
    if len(set(hashes.values()))!=4:
        raise ValueError('Two-lane candidates are not distinct')
    triggers={variants[name]['fallback_trigger']['metric'] for name in CANDIDATES[1:]}
    if len(triggers)!=3:raise ValueError('Two-lane fallback triggers are not distinct')
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,
            'candidate_sha256':hashes,'same_direction_lane_ids':[-1,-2],
            'physical_lane_availability_verified':False,
            'selected_delivery_claimed':False}


if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
