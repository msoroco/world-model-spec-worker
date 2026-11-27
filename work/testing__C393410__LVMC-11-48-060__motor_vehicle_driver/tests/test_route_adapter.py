"""Exercise actual vehicle/prop creation calls and observed enroute transfer."""
from __future__ import annotations

import math
import unittest
from types import SimpleNamespace as NS

from route_adapter import configure,step,sample,teardown


class Location:
    def __init__(self,x=0.,y=0.,z=0.):self.x,self.y,self.z=x,y,z


class Rotation:
    def __init__(self,**values):self.yaw=values.get('yaw',0.)


class Transform:
    def __init__(self,location,rotation=None):self.location=location;self.rotation=rotation or Rotation()


class VehicleControl:
    def __init__(self,**values):self.values=values


class Actor:
    def __init__(self,kind,transform,identifier):self.type_id=kind;self.transform=transform;self.id=identifier;self.is_alive=True;self.controls=[]
    def set_autopilot(self,value):self.autopilot=value
    def get_transform(self):return self.transform
    def set_transform(self,value):self.transform=value
    def get_velocity(self):return NS(x=0.,y=0.,z=0.)
    def apply_control(self,value):self.controls.append(value.values)
    def destroy(self):self.is_alive=False


class World:
    def __init__(self):self.actors=[]
    def get_blueprint_library(self):return NS(find=lambda kind:NS(id=kind))
    def try_spawn_actor(self,bp,pose):
        actor=Actor(bp.id,pose,len(self.actors)+1);self.actors.append(actor);return actor
    def get_map(self):return NS(get_waypoint=lambda location,project_to_road=False:NS(road_id=20))


class AdapterTests(unittest.TestCase):
    def test_vehicle_and_pickup_prop_transfer(self):
        carla=NS(Location=Location,Rotation=Rotation,Transform=Transform,VehicleControl=VehicleControl)
        packet={'itinerary':{'waypoints_xy_m':[[0.,0.],[10.,0.],[20.,0.]],'spawn_xyz_m':[0.,0.,0.],
            'vehicle_blueprint':'vehicle.test.car'},'enroute_purpose':{'kind':'pick_up'},
            'activity_protocol':{'kind':'pick_up','premises_xyz_m':[1.,0.,0.],'prop_blueprint':'static.prop.box'},
            'site':{'truck_routes':{'origin':{'road_id':10},'destination':{'road_id':30}},
                'intervening_street':{'road_id':20,'designation':'non_truck'}}}
        world=World();handle=configure(world,carla,packet,4.)
        self.assertEqual([a.type_id for a in world.actors],['vehicle.test.car','static.prop.box'])
        self.assertFalse(handle['vehicle'].autopilot)
        seen=[]
        for index in range(20):
            step(handle,carla)
            seen.append(sample(world,handle,packet,index+1,(index+1)*.05)['activity_kind'])
        self.assertEqual(seen.count('pick_up'),1)
        self.assertTrue(any(control.get('brake')==1. for control in handle['vehicle'].controls))
        self.assertTrue(math.isclose(handle['prop'].get_transform().location.x,0.))
        teardown(handle)
        self.assertFalse(any(actor.is_alive for actor in world.actors))


if __name__=='__main__':unittest.main()
