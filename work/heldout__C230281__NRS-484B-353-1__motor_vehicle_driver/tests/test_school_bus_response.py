import json
import tempfile
import unittest
from pathlib import Path
import sys
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_bus_response import measure, audit_motion_comparison
from school_bus_controller import BRANCHES, target, apply, motion_readback, spawn_meeting_scene, select_meeting_waypoints
from school_bus_camera import CAMERAS, LosslessSourceSink, SchoolBusCameraCapture
from school_bus_native import CASE_ID, check_plan, check_scene, close_all


def corners(x):
    return [[x-1,-.5],[x+1,-.5],[x+1,.5],[x-1,.5]]


class SourceResponse(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.context={'bus_id':'bus','subject_id':'car','approach':'meeting',
                      'bus_stopped':True,'pupil_stop_purpose':True,'signs_equipped':True,
                      'divided_other_roadway':False,'traffic_officer_control':False}
        self.signal=[];self.motion=[]
        for i,(active,phase,speed,x) in enumerate(zip(
            (False,True,True,True,False,False),
            (False,True,False,True,False,False),
            (5,5,0,0,2,3),
            (-6,-5,-4,-3,-2,4))):
            self.signal.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus',
                'red_signal_operating':active,'red_phase_on':phase,
                'front_red_visible':phase,'rear_red_visible':phase})
            self.motion.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus','subject_id':'car',
                'subject_speed_mps':speed,'subject_corners':corners(x),
                'bus_corners':corners(0),'travel_tangent_xy':[1,0]})
    def write(self):
        paths=[]
        for name,value in (('context',self.context),('signal',self.signal),('motion',self.motion)):
            path=self.root/(name+'.json');path.write_text(json.dumps(value)+'\n');paths.append(path)
        return paths
    def result(self):
        return measure(*self.write())
    def test_meeting_holds_through_red_and_passes_after_cessation(self):
        result=self.result()
        self.assertEqual((result['red_onset_frame'],result['red_cessation_frame']),(101,104))
        self.assertEqual((result['first_stop_frame'],result['first_full_body_pass_frame']),(102,105))
        self.assertTrue(result['held_stop_until_cessation'])
        self.assertIsNone(result['premature_restart_frame'])
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertIsNone(result['legal_conclusion'])
        self.assertEqual(set(result['source_sha256']),{'context','signal','motion'})
    def test_overtaking_opposite_tangent_and_premature_restart(self):
        self.context['approach']='overtaking'
        for row in self.motion:
            row['travel_tangent_xy']=[-1,0]
            row['subject_corners']=corners(-row['subject_corners'][0][0]-1)
        self.motion[3]['subject_speed_mps']=2
        result=self.result()
        self.assertEqual(result['premature_restart_frame'],103)
        self.assertFalse(result['held_stop_until_cessation'])
        self.assertEqual(result['first_full_body_pass_frame'],105)
    def test_active_red_pass_and_missing_sources(self):
        self.motion[3]['subject_corners']=corners(4)
        self.assertEqual(self.result()['first_full_body_pass_frame'],103)
        paths=self.write();paths[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            measure(*paths)
    def test_rejects_signal_and_frame_contradictions(self):
        self.signal[3]['rear_red_visible']=False
        with self.assertRaisesRegex(ValueError,'front and rear'):self.result()
        self.signal[3]['rear_red_visible']=True
        self.signal[2]['red_phase_on']=True
        self.signal[2]['front_red_visible']=True
        self.signal[2]['rear_red_visible']=True
        with self.assertRaisesRegex(ValueError,'alternation'):self.result()
        self.signal[2]['red_phase_on']=False
        self.motion[2]['time_s']=.105
        with self.assertRaisesRegex(ValueError,'frames differ'):self.result()
        self.motion[2]['time_s']=.1
        self.motion[2]['subject_corners']=[[0,0]]
        with self.assertRaisesRegex(ValueError,'body corners'):self.result()

    def test_all_selected_controller_branches_and_actual_apply_call(self):
        self.assertEqual(len(BRANCHES),8)
        class Vehicle:
            applied=None
            def apply_control(self, control):self.applied=control
        vehicle=Vehicle()
        for branch in BRANCHES:
            before=target(branch,red_signal_operating=True,stop_observed=False)
            after=target(branch,red_signal_operating=True,stop_observed=True)
            if branch=='meeting_restart_before_red_ceases':
                self.assertEqual((before['target_speed_mps'],after['target_speed_mps']),(0,5))
            elif branch in ('meeting_stop','overtaking_stop','meeting_resume_after_red_ceases'):
                self.assertEqual(before['target_speed_mps'],0)
            else:
                self.assertEqual(before['target_speed_mps'],5)
            self.assertIsNone(before['legal_conclusion'])
            control=apply(vehicle,dict,before,speed_mps=5)
            self.assertEqual(vehicle.applied,control)
            if before['target_speed_mps']==0:self.assertGreater(control['brake'],0)
            self.assertEqual(target(branch,red_signal_operating=False,stop_observed=True)['target_speed_mps'],5)
        with self.assertRaisesRegex(ValueError,'Unknown school-bus branch'):
            target('invented',red_signal_operating=True,stop_observed=False)

    def test_independent_motion_comparisons_and_fixed_source_rejection(self):
        baseline=self.write()
        variant_dir=self.root/'variant';variant_dir.mkdir()
        variant=[variant_dir/p.name for p in baseline]
        for source,destination in zip(baseline,variant):destination.write_bytes(source.read_bytes())
        restart=json.loads(variant[2].read_text())
        restart[3]['subject_speed_mps']=2
        variant[2].write_text(json.dumps(restart)+'\n')
        proof=audit_motion_comparison(baseline,variant,'premature_restart')
        self.assertEqual(proof['variant']['premature_restart_frame'],103)
        self.assertFalse(proof['physical_acceptance_claimed'])
        self.assertIsNone(proof['legal_conclusion'])
        with self.assertRaisesRegex(ValueError,'lacks passage during red'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        restart[3]['subject_corners']=corners(4)
        variant[2].write_text(json.dumps(restart)+'\n')
        self.assertEqual(audit_motion_comparison(baseline,variant,'pass_during_red')
                         ['variant']['first_full_body_pass_frame'],103)
        with self.assertRaisesRegex(ValueError,'lacks isolated early restart'):
            audit_motion_comparison(baseline,variant,'premature_restart')
        changed=json.loads(variant[1].read_text())
        changed[3]['red_phase_on']=False
        variant[1].write_text(json.dumps(changed)+'\n')
        with self.assertRaisesRegex(ValueError,'changed fixed original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        variant[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')

    def test_native_actor_motion_readback_and_opposite_tangent(self):
        class Vertex:
            def __init__(self,x,y,z):self.x=x;self.y=y;self.z=z
        class Bounds:
            def __init__(self,x):self.x=x
            def get_world_vertices(self,transform):
                return [Vertex(self.x+dx,dy,z) for z in (0,2)
                        for dx,dy in ((-1,-.5),(1,-.5),(1,.5),(-1,.5))]
        class Actor:
            def __init__(self,ident,x,speed=0):
                self.id=ident;self.bounding_box=Bounds(x);self.speed=speed
            def get_transform(self):return object()
            def get_velocity(self):return Vertex(self.speed,0,0)
        subject,bus=Actor('car',-5,2),Actor('bus',0)
        row=motion_readback(subject,bus,[1,0],100,0.0)
        self.assertEqual((row['subject_id'],row['bus_id'],row['subject_speed_mps']),('car','bus',2))
        self.assertEqual(len(row['subject_corners']),4)
        self.assertEqual(len(row['bus_corners']),4)
        self.assertLess(max(p[0] for p in row['subject_corners']),min(p[0] for p in row['bus_corners']))
        reverse=motion_readback(subject,bus,[-1,0],101,.05)
        self.assertEqual(reverse['travel_tangent_xy'],[-1.0,0.0])
        with self.assertRaisesRegex(ValueError,'tangent'):
            motion_readback(subject,bus,[0,0],102,.1)
        subject.bounding_box.get_world_vertices=lambda transform: []
        with self.assertRaisesRegex(ValueError,'body vertices'):
            motion_readback(subject,bus,[1,0],102,.1)

    def test_four_camera_creation_source_encoding_and_frame_join(self):
        class Blueprint:
            def __init__(self):self.attrs={}
            def set_attribute(self,key,value):self.attrs[key]=value
        class Library:
            def find(self,key):
                self.assert_key=key
                return Blueprint()
        class Sensor:
            def __init__(self):self.callback=None;self.stopped=False;self.destroyed=False
            def listen(self,callback):self.callback=callback
            def stop(self):self.stopped=True
            def destroy(self):self.destroyed=True
        class World:
            def __init__(self):self.spawned=[]
            def get_blueprint_library(self):return Library()
            def spawn_actor(self,blueprint,transform,attach_to):
                sensor=Sensor();self.spawned.append((blueprint,transform,attach_to,sensor));return sensor
        class Carla:
            @staticmethod
            def Location(*values):return values
            @staticmethod
            def Rotation(*values):return values
            @staticmethod
            def Transform(location,rotation):return (location,rotation)
        class Sink:
            def __init__(self):self.frames=[]
            def write(self,image):self.frames.append(image.frame)
        class Image:
            def __init__(self,frame,size):self.frame=frame;self.width,self.height=size
        subject,bus=object(),object()
        world=World();sinks={name:Sink() for name in CAMERAS}
        cameras=SchoolBusCameraCapture(world,Carla,subject,bus,sinks)
        self.assertEqual(len(world.spawned),4)
        self.assertEqual({name for name in CAMERAS},{'overview','approach','reference_corner','driver_reference'})
        for name,(_,_,parent,sensor) in zip(CAMERAS,world.spawned):
            self.assertIs(parent,subject if name=='approach' else bus)
            self.assertEqual(world.spawned[list(CAMERAS).index(name)][0].attrs['sensor_tick'],'0.05')
            sensor.callback(Image(101,CAMERAS[name][3]))
        cameras.wait_for_frame(101,timeout_s=.01)
        self.assertEqual(cameras.verify([101]),{name:1 for name in CAMERAS})
        with self.assertRaisesRegex(ValueError,'Missing or extra original'):
            cameras.verify([101,102])
        world.spawned[0][3].callback(Image(101,CAMERAS['overview'][3]))
        with self.assertRaisesRegex(ValueError,'callback failed'):
            cameras.wait_for_frame(101,timeout_s=.01)
        cameras.close()
        self.assertTrue(all(row[3].stopped and row[3].destroyed for row in world.spawned))

        class Pipe:
            def __init__(self):self.writes=[];self.closed=False
            def write(self,data):self.writes.append(len(data))
            def close(self):self.closed=True
        class Process:
            def __init__(self):self.stdin=Pipe()
            def wait(self):return 0
        calls=[]
        def popen(command,stdin):
            calls.append((command,stdin));return Process()
        source=LosslessSourceSink(self.root,'overview',popen=popen)
        class Data:
            def __init__(self,n):self.n=n
            def __len__(self):return self.n
        class RawImage:pass
        image=RawImage();image.raw_data=Data(source.frame_bytes)
        source.write(image)
        image.raw_data=Data(source.frame_bytes-1)
        with self.assertRaisesRegex(ValueError,'byte count'):
            source.write(image)
        source.close()
        self.assertEqual(calls[0][0][0],'ffmpeg')
        self.assertTrue(source.process.stdin.closed)

    def test_meeting_actor_construction_opposite_road_and_cleanup(self):
        class Vector:
            def __init__(self,x):self.x=x;self.y=0
        class Transform:
            def __init__(self,location):self.location=location
            def get_forward_vector(self):return Vector(self.location.heading)
        class Location:
            def __init__(self,heading,road=7,x=0):
                self.heading=heading;self.road=road;self.x=x;self.y=0
        class Waypoint:
            def __init__(self,location):
                self.road_id=location.road;self.is_junction=False
                self.transform=Transform(location)
        class Mapping:
            def get_waypoint(self,location):return Waypoint(location)
        class Library:
            def find(self,name):return name
        class Actor:
            def __init__(self):self.control=None;self.destroyed=False
            def apply_control(self,control):self.control=control
            def destroy(self):self.destroyed=True
        class World:
            def __init__(self):self.actors=[];self.fail_second=False
            def get_map(self):return Mapping()
            def get_blueprint_library(self):return Library()
            def try_spawn_actor(self,blueprint,transform):
                if self.fail_second and len(self.actors)==1:return None
                actor=Actor();self.actors.append((blueprint,transform,actor));return actor
        class Carla:
            @staticmethod
            def VehicleControl(**keys):return keys
        scene={'bus_blueprint_id':'vehicle.school_bus','subject_blueprint_id':'vehicle.car',
               'bus_transform':Transform(Location(-1,x=20)),
               'subject_transform':Transform(Location(1))}
        world=World()
        built=spawn_meeting_scene(world,Carla,scene)
        self.assertEqual([item[0] for item in world.actors],
                         ['vehicle.school_bus','vehicle.car'])
        self.assertEqual(built['heading_dot'],-1)
        self.assertTrue(world.actors[0][2].control['hand_brake'])
        self.assertFalse(built['bus_equipment_verified'])
        self.assertFalse(built['undivided_road_verified'])
        self.assertEqual(built['initial_forward_separation_m'],20)
        scene['subject_transform']=Transform(Location(-1))
        with self.assertRaisesRegex(ValueError,'opposite travel'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1,8))
        with self.assertRaisesRegex(ValueError,'one nonjunction road'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1,x=19))
        with self.assertRaisesRegex(ValueError,'ahead of subject'):
            spawn_meeting_scene(World(),Carla,scene)
        scene['subject_transform']=Transform(Location(1))
        failed=World();failed.fail_second=True
        with self.assertRaisesRegex(ValueError,'subject spawn failed'):
            spawn_meeting_scene(failed,Carla,scene)
        self.assertTrue(failed.actors[0][2].destroyed)

    def test_first_exact_native_check_is_carla_lazy(self):
        package=Path(__file__).resolve().parents[1]
        plan=json.loads((package/'case-plan.json').read_text())
        self.assertTrue(check_plan(plan,CASE_ID))
        scene={'bus_blueprint_id':'vehicle.school_bus',
               'subject_blueprint_id':'vehicle.car',
               'bus':{'location':[20,0,0],'rotation':[0,180,0]},
               'subject':{'location':[0,0,0],'rotation':[0,0,0]}}
        self.assertIs(check_scene(scene),scene)
        with self.assertRaisesRegex(ValueError,'pose missing'):
            check_scene({**scene,'subject':{'location':[0,0,0]}})
        source=self.root/'scene.json';source.write_text(json.dumps(scene)+'\n')
        command=[sys.executable,str(package/'school_bus_native.py'),'--check',
                 '--plan',str(package/'case-plan.json'),'--scene',str(source),
                 '--case-id',CASE_ID]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.root/'capture').exists())

    def test_native_cleanup_runs_restoration_after_encoder_failure(self):
        calls=[]
        def bad_encoder():
            calls.append('encoder')
            raise ValueError('encoder failed')
        with self.assertRaisesRegex(RuntimeError,'encoder'):
            close_all([('encoder',bad_encoder),
                       ('actor',lambda:calls.append('actor')),
                       ('world_settings_restore',lambda:calls.append('restore'))])
        self.assertEqual(calls,['encoder','actor','restore'])

    def test_map_selected_meeting_route_and_auto_scene_contract(self):
        class Vector:
            def __init__(self,x):self.x=x;self.y=0
        class Location:
            def __init__(self,x,y):self.x=x;self.y=y
        class Transform:
            def __init__(self,x,y,heading):self.location=Location(x,y);self.heading=heading
            def get_forward_vector(self):return Vector(self.heading)
        class Waypoint:
            def __init__(self,road,lane,s,x,y,heading):
                self.road_id=road;self.lane_id=lane;self.s=s;self.is_junction=False
                self.transform=Transform(x,y,heading)
        class Mapping:
            rows=[Waypoint(7,1,0,0,0,1),Waypoint(7,-1,23,23,4,-1),
                  Waypoint(8,1,0,0,0,1)]
            def generate_waypoints(self,distance):
                self.distance=distance;return self.rows
        mapping=Mapping()
        found=select_meeting_waypoints(mapping)
        self.assertEqual((found['road_id'],found['subject_waypoint'].lane_id,
                          found['bus_waypoint'].lane_id),(7,-1,1))
        self.assertEqual(mapping.distance,4.0)
        auto={'bus_blueprint_id':'vehicle.school_bus',
              'subject_blueprint_id':'vehicle.car','auto_meeting_route':True}
        self.assertIs(check_scene(auto),auto)
        with self.assertRaisesRegex(ValueError,'mixes automatic'):
            check_scene({**auto,'bus':{}})
        mapping.rows=[Waypoint(7,1,0,0,0,1)]
        with self.assertRaisesRegex(ValueError,'No two-way'):
            select_meeting_waypoints(mapping)

if __name__=='__main__':unittest.main()
