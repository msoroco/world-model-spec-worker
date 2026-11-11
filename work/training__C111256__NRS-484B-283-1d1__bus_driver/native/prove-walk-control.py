"""CPU construction proof for source-fed bus Walk hold requests, not physical acceptance."""
from dataclasses import replace
import json
import math
import xml.etree.ElementTree as ET

from cameras import camera_plan
from controller import EngineeringKnobs, PathController, WalkFrame, WalkYieldController
from geometry import check, open_drive, pedestrian_route, route


def require(ok, message):
    if not ok:
        raise ValueError(message)


def run():
    geometry=check()
    xml=ET.fromstring(open_drive())
    require(xml.find(".//signal[@id='620']") is not None and
            xml.find(".//object[@type='crosswalk']") is not None,
            'Walk signal or physical crosswalk missing from authored road')
    require(min(math.dist(p,[1.75,-11]) for p in pedestrian_route())<=.051,
            'Pedestrian route does not enter bus lane')
    cams={v['name'] for v in camera_plan('primary')}
    require(cams=={'overview','approach','reference_corner','driver_reference'},
            'Current source camera inventory differs')
    def path():return PathController(route(),3.8,35,EngineeringKnobs())
    sample=WalkFrame(native_frame=20, signal_actor_id=620,pedestrian_actor_id=720,
                     display='Walk',pedestrian_facing_signal=True,
                     pedestrian_in_crosswalk=True,pedestrian_xy_m=(1.7,-11),
                     bus_front_y_m=-14,provenance='synthetic_native_sample')
    def step(policy,obs):
        return WalkYieldController(path(),policy=policy).step(
            observation=obs,position_xy_m=(1.75,-18),yaw_rad=math.pi/2,
            speed_mps=3,dt_s=.05)
    reference=step('yield_request',sample)
    contrast=step('no_yield_request',sample)
    require(reference['hold_requested'] and reference['throttle']==0 and reference['brake']==1 and
            reference['requested_speed_mps']==0 and not reference['physical_yield_observed'] and
            not reference['legal_outcome_claimed'], 'Reference hold request missing or overclaimed')
    require(not contrast['hold_requested'] and contrast['requested_speed_mps']>0 and
            contrast['walk_crossing_source_observed'], 'Contrast policy did not isolate yield request')
    for changed in (replace(sample,display='DontWalk'),replace(sample,pedestrian_facing_signal=False),
                    replace(sample,pedestrian_in_crosswalk=False),replace(sample,pedestrian_xy_m=(1.7,-20)),
                    replace(sample,bus_front_y_m=-10)):
        require(not step('yield_request',changed)['hold_requested'],
                'Inactive or already-entered crossing issued a hold')
    rejected=0
    for changed in (replace(sample,provenance='invented_original'),replace(sample,signal_actor_id=720),
                    replace(sample,native_frame=-1),replace(sample,display='green'),
                    replace(sample,pedestrian_xy_m=(float('nan'),-11))):
        try:step('yield_request',changed)
        except ValueError:rejected+=1
        else:raise ValueError('Invalid original-source claim accepted')
    return {'authored_geometry':geometry,'source_camera_count':len(cams),
            'reference_hold_requested':True,'contrast_hold_requested':False,
            'inactive_crossing_checks':5,'invalid_source_rejections':rejected,
            'physical_completion_observed':False,'legal_outcome_claimed':False}


if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True))
