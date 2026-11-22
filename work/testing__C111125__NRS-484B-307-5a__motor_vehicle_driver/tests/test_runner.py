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
        decision=runner.yield_decision(self.scene,people,signal_exhibited_frame=10,current_frame=12)
        self.assertFalse(decision['hold_at_stop_line'])
        self.assertEqual(runner.command(self.scene,-10,decision)['intended_maneuver'],'straight')
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
