import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('arrow_runner',ROOT/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def participant(identifier,role,x,y,lawful=True):
    return {'id':identifier,'role':role,
            'body_vertices_m':[[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]],
            'lawfully_present':lawful,'lawful_presence_source':'original phase and right-of-way context'}


class ArrowControllerTests(unittest.TestCase):
    def setUp(self):self.scene=runner.load_scene()
    def test_spawns_clear_and_occupied_actor_geometry(self):
        class Actor:
            def destroy(self):self.destroyed=True
        class Library:
            def filter(self,pattern):return [pattern]
        class World:
            def __init__(self):self.calls=[]
            def get_blueprint_library(self):return Library()
            def spawn_actor(self,blueprint,transform):
                self.calls.append((blueprint,transform));return Actor()
        for occupancy,positions in [('clear',(-30,35,35)),('lawfully_present',(-30,0,9))]:
            world=World();scene=dict(self.scene,participant_occupancy_setup=occupancy)
            actors=runner.spawn_scene(world,scene,lambda *values:values)
            self.assertEqual(set(actors),{'ego','vehicle','pedestrian'})
            self.assertEqual(tuple(call[1][0] for call in world.calls),positions)
            self.assertEqual(world.calls[-1][0],'walker.pedestrian.*')
            if occupancy=='lawfully_present':
                self.assertEqual(tuple(call[1][1] for call in world.calls),(0,-12,-9))
                self.assertEqual(tuple(call[1][3] for call in world.calls),(0,90,90))
    def test_predeclared_arrow_exhibition_follows_participant_entry_window(self):
        self.assertEqual(runner.authored_arrow_state(self.scene,0),'Red')
        self.assertEqual(runner.authored_arrow_state(self.scene,4.95),'Red')
        self.assertEqual(runner.authored_arrow_state(self.scene,5.0),'Green')
        self.assertEqual(runner.authored_arrow_state(self.scene,6.0),'Green')
        with self.assertRaises(ValueError):runner.authored_arrow_state(self.scene,float('nan'))
        for y,speed in ((-12,2),(-9,1.5)):
            entry_time=(-5-y)/speed
            exit_time=(5-y)/speed
            self.assertLess(entry_time,self.scene['arrow_exhibition_after_s'])
            self.assertGreater(exit_time,self.scene['arrow_exhibition_after_s'])
    def test_occupied_participants_have_bounded_clearance_motion(self):
        occupied=dict(self.scene,participant_occupancy_setup='lawfully_present')
        clear=dict(self.scene,participant_occupancy_setup='clear')
        move=runner.participant_motion(occupied,0)
        self.assertGreater(move['vehicle_velocity_xyz_mps'][1],0)
        self.assertGreater(move['pedestrian_speed_mps'],0)
        self.assertGreater(move['pedestrian_direction_xyz'][1],0)
        self.assertEqual(runner.participant_motion(clear,0)['vehicle_velocity_xyz_mps'],(0.,0.,0.))
        with self.assertRaises(ValueError):runner.participant_motion(occupied,float('nan'))
        class Actor:
            def set_target_velocity(self,value):self.velocity=value
            def apply_control(self,value):self.control=value
        class Carla:
            @staticmethod
            def Vector3D(**value):return value
            @staticmethod
            def WalkerControl(**value):return value
        actors={'vehicle':Actor(),'pedestrian':Actor()}
        runner.apply_participant_motion(occupied,actors,Carla,2.)
        self.assertEqual(actors['vehicle'].velocity['y'],2.)
        self.assertEqual(actors['pedestrian'].control['speed'],1.5)
    def test_predeclared_alternate_head_selection(self):
        def head(ident,verified=True,facing=True):
            return {'source_verified':verified,'source_ref':'original/head-stream',
                    'head_id':ident,'observed_frame':18,'faces_ego_approach':facing,
                    'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}
        heads=[head(8),head(7)]
        primary=dict(self.scene,candidate_head_slot=0)
        self.assertEqual(runner.select_facing_head(primary,heads,frame=18)['head_id'],7)
        alternate=dict(self.scene,candidate_head_slot=1)
        self.assertEqual(runner.select_facing_head(alternate,heads,frame=18)['head_id'],8)
        with self.assertRaises(ValueError):
            runner.select_facing_head(alternate,[head(7),head(8,verified=False)],frame=18)
        with self.assertRaises(ValueError):
            runner.select_facing_head(alternate,[head(7),head(8,facing=False)],frame=18)
        with self.assertRaises(ValueError):
            runner.select_facing_head(primary,[head(7,verified=False),head(8)],frame=18)
        self.assertEqual(runner.select_facing_head(alternate,[head(7,verified=False),head(8)],frame=18)['head_id'],8)
    def test_sole_arrow_requires_exact_facing_source(self):
        aspect={'source_verified':True,'source_ref':'native/head-readback.json',
                'head_id':7,'observed_frame':18,
                'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}
        self.assertIs(runner.require_sole_straight_arrow(aspect,head_id=7,frame=18),aspect)
        for change in ({'source_verified':False},
                       {'illuminated_indications':[{'color':'green','shape':'circle','direction':'all'}]},
                       {'illuminated_indications':aspect['illuminated_indications']+[{'color':'green','shape':'arrow','direction':'left'}]},
                       {'head_id':8},{'observed_frame':19}):
            with self.assertRaises(ValueError):
                runner.require_sole_straight_arrow(dict(aspect,**change),head_id=7,frame=18)
    def test_yield_for_vehicle_and_pedestrian_in_governed_regions(self):
        people=[participant('car','vehicle',0,0),participant('walker','pedestrian',9,0)]
        decision=runner.yield_decision(self.scene,people,signal_exhibited_frame=10,current_frame=12)
        self.assertEqual(decision['occupied_by'],['car','walker'])
        self.assertEqual(runner.command(self.scene,-10,decision)['brake'],1.0)
    def test_clear_region_can_proceed_straight(self):
        people=[participant('car','vehicle',30,30)]
        people[0]['lawfully_present']=None;people[0]['lawful_presence_source']=None
        decision=runner.yield_decision(self.scene,people,signal_exhibited_frame=10,current_frame=12)
        self.assertFalse(decision['hold_at_stop_line'])
        self.assertEqual(runner.command(self.scene,-10,decision)['intended_maneuver'],'straight')
    def test_next_tick_control_fails_closed_then_proceeds_on_verified_clear_frame(self):
        ego=[[-11,-.5,0],[-10,-.5,0],[-10,.5,0],[-11,.5,0]]
        person=participant('car','vehicle',35,0)
        person['lawfully_present']=None;person['lawful_presence_source']=None
        aspect={'source_verified':True,'source_ref':'reviewed original asset',
                'head_id':7,'observed_frame':18,
                'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}
        signal={'frame':18,'facing_head_id':7,'aspect':aspect}
        clear=runner.control_step(self.scene,signal,[person],ego)
        self.assertEqual(clear['reason'],'straight_clear')
        self.assertGreater(clear['control']['throttle'],0)
        self.assertEqual(clear['first_arrow_frame'],18)
        inside=dict(person,body_vertices_m=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]])
        unknown=runner.control_step(self.scene,signal,[inside],ego)
        self.assertEqual(unknown['reason'],'unverified_exhibition_lawfulness')
        self.assertEqual(unknown['control']['brake'],1)
        later=runner.control_step(self.scene,dict(signal,frame=19,
            aspect=dict(aspect,observed_frame=19)),
            [dict(inside,lawfully_present=True,lawful_presence_source='late review')],ego,
            first_arrow_frame=unknown['first_arrow_frame'],
            exhibition_occupants=unknown['exhibition_occupants'])
        self.assertEqual(later['reason'],'unverified_exhibition_lawfulness')
        lawful=dict(inside,lawfully_present=True,lawful_presence_source='original phase context')
        held=runner.control_step(self.scene,signal,[lawful],ego)
        self.assertEqual(held['reason'],'yield_hold')
        self.assertEqual(held['exhibition_occupants'],['car'])
        changed=dict(lawful,lawfully_present=False)
        still=runner.control_step(self.scene,dict(signal,frame=19,
            aspect=dict(aspect,observed_frame=19)),[changed],ego,
            first_arrow_frame=held['first_arrow_frame'],
            exhibition_occupants=held['exhibition_occupants'])
        self.assertEqual(still['reason'],'yield_hold')
        unverified=dict(signal,aspect=dict(aspect,source_verified=False))
        self.assertEqual(runner.control_step(self.scene,unverified,[person],ego)['reason'],'unverified_sole_arrow')
    def test_lawful_presence_and_body_sources_required(self):
        person=participant('walker','pedestrian',0,0)
        del person['lawful_presence_source']
        with self.assertRaises(ValueError):runner.yield_decision(self.scene,[person],signal_exhibited_frame=10,current_frame=12)
        person=participant('walker','pedestrian',0,0);person['body_vertices_m']=[]
        with self.assertRaises(ValueError):runner.yield_decision(self.scene,[person],signal_exhibited_frame=10,current_frame=12)
    def test_yield_after_line_is_rejected(self):
        decision=runner.yield_decision(self.scene,[participant('car','vehicle',0,0)],signal_exhibited_frame=10,current_frame=12)
        with self.assertRaises(ValueError):runner.command(self.scene,0,decision)


if __name__=='__main__':unittest.main()
