import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


crossing = module('native_crossing')
control = module('pedestrian_control')
comparison = module('comparison_audit')
sys.path.insert(0, str(ROOT))
measurement = module('saved_measurement')


class CrossingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.refs = [
            self.write('map.json', json.dumps({'public_highway':True, 'highway_polygon_xy':[[0,0],[10,0],[10,10],[0,10]],
                                               'crosswalk_polygon_xy':[[0,4],[10,4],[10,6],[0,6]],
                                               'crosswalk_kind':'marked', 'crosswalk_qualifies':True})),
            self.write('head.json', json.dumps({'official':True,'control':'traffic_light','head_id':'head1','pedestrian_faces_head':True})),
            self.write('devices.json', json.dumps({'other_device_id':'ped1','inventory_complete':True})),
        ]
        self.site = {
            'cell_id': 'C111125', 'actor': 'pedestrian', 'original_sources': self.refs,
            'map_source_path': 'map.json', 'signal_source_path': 'head.json',
            'device_inventory_source_path': 'devices.json', 'official_signal_head_id': 'head1',
            'pedestrian_faces_head': True, 'public_highway_source_assertion': True,
            'crosswalk_kind': 'marked', 'crosswalk_qualification_source_assertion': True,
            'highway_polygon_xy': [[0,0],[10,0],[10,10],[0,10]],
            'crosswalk_polygon_xy': [[0,4],[10,4],[10,6],[0,6]],
            'pedestrian_route_xy': [[-2,5],[2,5],[11,5]], 'other_device_id': 'ped1',
            'pedestrian_blueprint_id': 'walker.pedestrian.0001', 'pedestrian_spawn_xyz': [-2,5,0],
        }

    def write(self, name, text):
        path = self.root / name
        path.write_text(text)
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def events(self, device='none', aspects=None, entry_xy=(2,5)):
        aspects = ['circular_green'] if aspects is None else aspects
        rows = [
            {'frame': f, 'official_signal_head_id': 'head1', 'pedestrian_faces_head': True,
             'lit_aspects': aspects, 'pedestrian_xy': xy, 'other_device_id': 'ped1',
             'other_device_indication': device}
            for f, xy in ((0, [-2,5]), (1, entry_xy))]
        return self.write('frames.json', json.dumps(rows))

    def test_marked_crossing_reads_original_frames(self):
        result = crossing.measure(self.site, self.root, self.events())
        self.assertEqual(result['first_highway_entry']['frame'], 1)
        self.assertTrue(result['first_highway_entry']['in_crosswalk'])
        self.assertFalse(result['physical_acceptance'])

    def test_unmarked_crossing_requires_source_qualification(self):
        self.site['crosswalk_kind'] = 'unmarked'
        self.site['crosswalk_qualification_source_assertion'] = False
        with self.assertRaises(crossing.SourceError):
            crossing.verify_site(self.site, self.root)

    def test_unmarked_crossing_source_geometry_binding(self):
        self.site['crosswalk_kind'] = 'unmarked'
        map_data=json.loads((self.root/'map.json').read_text())
        map_data['crosswalk_kind']='unmarked'
        self.site['original_sources'][0]=self.write('map.json',json.dumps(map_data))
        self.assertTrue(crossing.verify_site(self.site,self.root))
        map_data['crosswalk_qualifies']=False
        self.site['original_sources'][0]=self.write('map.json',json.dumps(map_data))
        with self.assertRaises(crossing.SourceError):
            crossing.verify_site(self.site,self.root)

    def test_other_device_state_is_measured(self):
        result = crossing.measure(self.site, self.root, self.events('DONT_WALK'))
        self.assertEqual(result['first_highway_entry']['other_device_indication'], 'DONT_WALK')

    def test_outside_route_and_entry(self):
        self.site['route_crosswalk_expected'] = False
        self.site['pedestrian_route_xy'] = [[-2,8],[2,8],[11,8]]
        result = crossing.measure(self.site, self.root, self.events(entry_xy=(2,8)))
        self.assertFalse(result['first_highway_entry']['in_crosswalk'])

    def test_reject_changed_hash_and_identity(self):
        ref = self.events()
        (self.root / 'frames.json').write_text('[]')
        with self.assertRaises(crossing.SourceError):
            crossing.measure(self.site, self.root, ref)
        self.site['official_signal_head_id'] = 'different'
        with self.assertRaises(crossing.SourceError):
            crossing.measure(self.site, self.root, self.events())

    def test_reject_wrong_facing_and_missing_highway(self):
        self.site['pedestrian_faces_head'] = False
        with self.assertRaises(crossing.SourceError):
            crossing.verify_site(self.site, self.root)
        self.site['pedestrian_faces_head'] = True
        self.site['pedestrian_route_xy'] = [[-2,5],[-3,5],[-4,5]]
        with self.assertRaises(crossing.SourceError):
            crossing.verify_site(self.site, self.root)

    def test_control_wait_and_cross(self):
        factory = lambda **kw: kw
        vector = lambda *xyz: xyz
        self.assertEqual(control.target_control('other_device_stop', self.site, (-2,5), factory, vector)['speed'], 0)
        moving = control.target_control('marked_cross', self.site, (-2,5), factory, vector)
        self.assertGreater(moving['direction'][0], 0)
        self.assertEqual(moving['speed'], 1.2)

    def test_spawn_readback_and_cleanup(self):
        class BlueprintLibrary:
            def find(self, identity):
                return identity
        class Actor:
            type_id = 'walker.pedestrian.0001'
            destroyed = False
            def get_transform(self):
                return object()
            def destroy(self):
                self.destroyed = True
        actor = Actor()
        class World:
            def try_spawn_actor(self, blueprint, transform):
                self.blueprint = blueprint
                self.transform = transform
                return actor
        world = World()
        self.assertIs(crossing.spawn_pedestrian(world, self.site, self.root, BlueprintLibrary(), lambda *xyz: xyz), actor)
        self.assertEqual(world.transform, (-2,5,0))
        actor.type_id = 'wrong'
        with self.assertRaises(crossing.SourceError):
            crossing.spawn_pedestrian(world, self.site, self.root, BlueprintLibrary(), lambda *xyz: xyz)
        self.assertTrue(actor.destroyed)

    def test_comparison_rejects_fixed_condition_drift(self):
        common = {k: 'same' for k in ('map_source_sha256','signal_source_sha256','device_inventory_source_sha256',
                  'highway_polygon_source_sha256','camera_profile_sha256')}
        common['duration_frames'] = 2
        left = {**common, 'case_suffix':'marked_cross','crosswalk_kind':'marked','green_alone_frames':2,
                'first_highway_entry': {'other_device_indication':'none','in_crosswalk':True}}
        right = {**left, 'case_suffix':'unmarked_cross','crosswalk_kind':'unmarked'}
        self.assertFalse(comparison.audit_pair('marked_vs_unmarked', left, right)['physical_acceptance'])
        right['map_source_sha256'] = 'changed'
        with self.assertRaises(comparison.ComparisonError):
            comparison.audit_pair('marked_vs_unmarked', left, right)

    def test_comparison_rejects_missing_entry_source(self):
        common = {k: 'same' for k in ('map_source_sha256','signal_source_sha256','device_inventory_source_sha256',
                  'highway_polygon_source_sha256','camera_profile_sha256')}
        common['duration_frames'] = 2
        left = {**common, 'case_suffix':'marked_cross','crosswalk_kind':'marked','green_alone_frames':2,
                'first_highway_entry': {'other_device_indication':'none','in_crosswalk':True}}
        right = {**left, 'case_suffix':'outside_cross','first_highway_entry':None}
        with self.assertRaises(comparison.ComparisonError):
            comparison.audit_pair('crosswalk_boundary', left, right)

    def test_contrary_device_pair_requires_measured_choice(self):
        common = {k: 'same' for k in ('map_source_sha256','signal_source_sha256','device_inventory_source_sha256',
                  'highway_polygon_source_sha256','camera_profile_sha256')}
        common['duration_frames'] = 2
        waiting = {**common, 'case_suffix':'other_device_stop','crosswalk_kind':'marked','green_alone_frames':2,
                   'first_highway_entry':None,'device_indication_while_waiting':'DONT_WALK'}
        crossing_case = {**common, 'case_suffix':'other_device_cross','crosswalk_kind':'marked','green_alone_frames':2,
                         'first_highway_entry':{'other_device_indication':'DONT_WALK','in_crosswalk':True}}
        self.assertFalse(comparison.audit_pair('contrary_device_choice',waiting,crossing_case)['physical_acceptance'])
        crossing_case['first_highway_entry']['other_device_indication']='unknown'
        with self.assertRaises(comparison.ComparisonError):
            comparison.audit_pair('contrary_device_choice',waiting,crossing_case)

    def test_green_alone_requires_single_aspect(self):
        result = crossing.measure(self.site,self.root,self.events(aspects=['circular_green','green_arrow']))
        self.assertFalse(result['first_highway_entry']['green_alone'])

    def test_frame_signal_identity_rejected(self):
        ref=self.events()
        rows=json.loads((self.root/'frames.json').read_text())
        rows[1]['official_signal_head_id']='other'
        ref=self.write('frames.json',json.dumps(rows))
        with self.assertRaises(crossing.SourceError):
            crossing.measure(self.site,self.root,ref)

    def test_saved_measurement_needs_sealed_original_sources(self):
        site_ref = self.write('site.json',json.dumps(self.site))
        event_ref = self.events()
        result = measurement.build(site_ref,event_ref,self.root)
        self.assertEqual(result['facts']['first_highway_entry']['frame'],1)
        self.assertFalse(result['physical_acceptance'])
        (self.root/'frames.json').write_text('[]')
        with self.assertRaises(ValueError):
            measurement.build(site_ref,event_ref,self.root)

    def test_reject_incomplete_device_inventory(self):
        self.site['original_sources'][2]=self.write('devices.json',json.dumps({'other_device_id':'ped1','inventory_complete':False}))
        with self.assertRaises(crossing.SourceError):
            crossing.verify_site(self.site,self.root)


if __name__ == '__main__':
    unittest.main()
