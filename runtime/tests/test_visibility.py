"""Any-body measurement, censoring, coverage and subject-relative attachment."""
import importlib.util
import os
import unittest
from pathlib import Path
from traffic_spec_adapter.visibility import sight_distance, attach_visibility, CONVENTION

base = Path(__file__).resolve().parents[1]
path = Path(os.environ.get('LAW_EVIDENCE_SOURCE', str(base/'python/carla_sgg/law_evidence.py')))
spec = importlib.util.spec_from_file_location('visibility_capture', path)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def synthetic_lane_topology(lanes):
    # These fake API routes stay inside a source-declared long modeled segment;
    # neither test claims terminal continuation from an absent topology API.
    definitions=''.join('<lane id="%s" type="driving"/>'%lane for lane in lanes)
    return '<OpenDRIVE><road id="9" length="2000" junction="-1"><lanes><laneSection s="0"><right>'+definitions+'</right></laneSection></lanes></road></OpenDRIVE>'


def measured(horizons):
    return {'visibility_criterion': 'any_of_nine_body_samples',
            'distance_convention': CONVENTION, 'horizon_tolerance_m': .25,
            'eye_height_m': 1.4, 'scan_step_m': 10., 'probe_distance_m': 152.4,
            'ego_body_samples_m': [[1.5,-1.5,.5]] + [[x,-y,z] for x in (1,2) for y in (1,2) for z in (0,1)],
            'ego_projection': {'road_id':1},
            'required_lane_ids': list(range(1,len(horizons)+1)),
            'approaches': [{'lane_id': i, 'any_sample_clear_at_probe': True,
                            'any_body_sight_horizon': h} for i, h in enumerate(horizons,1)]}


def boundary(low):
    return {'bound': 'first_sampled_occlusion', 'bracket_m': [low, low+.125],
            'distance_m': low+.0625}


def sdk_available():
    if importlib.util.find_spec('carla') is None:return False
    import carla
    return all(hasattr(carla,key) for key in ('BoundingBox','Transform','Location','Vector3D'))


class VisibilityTests(unittest.TestCase):
    def test_unselected_frames_keep_verified_actor_coverage(self):
        import itertools, json, tempfile
        from unittest.mock import patch
        from traffic_spec_adapter import visibility
        body = [list(v) for v in itertools.product((-1., 1.), repeat=3)]
        margin = 64*2**-23
        bounds = [{'actor_id': actor, 'low_m': [-1.-margin]*3,
                   'high_m': [1.+margin]*3} for actor in (1, 2)]
        participants = [{'actor_id': actor, 'blueprint': 'vehicle.test',
                         'body_vertices_m': body} for actor in (1, 2)]
        events = {i: {'actor_id': 1, 'recording_time_s': float(i),
                      'participants': participants} for i in (10, 11)}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = root/'recorder.txt'
            recorder.write_text(' Create 1: vehicle.test x\n Create 2: vehicle.test x\n Create 3: traffic.stop x\n')
            enclosure = root/'enclosures.jsonl'
            enclosure.write_text(''.join(json.dumps(dict(original_frame=i,
                actor_id=1, recording_time_s=float(i), bounds=bounds))+'\n'
                for i in (10, 11)))
            certificate = {'opaque_vehicle_enclosures': {},
                'opaque_enclosure_model': 'original_vehicle_body_bbox_v1',
                'native_actor_registry': {'1': 'vehicle.test', '2': 'vehicle.test',
                                          '3': 'traffic.stop'}}
            inventory = {'observer_query_method': 'native_incoming_route_positions_v1',
                'observer_query_recording_frame_count': 2,
                'observer_query_frames': [{'original_frame': 10, 'lanes': []}]}
            with patch('traffic_spec_adapter.body_capture.acquisition_contract'), patch.object(
                    visibility, '_source_reference_component_models', return_value={}):
                result, _ = visibility._source_vehicle_enclosures(certificate,
                    {'capture/recorder_info.txt': recorder}, events,
                    {'frames': [{'original_frame': 10}]}, lambda *args: enclosure,
                    inventory, static_actors=(3,))
                self.assertEqual(result[11], [bounds[1]])
                self.assertEqual({1, 3} | {b['actor_id'] for b in result[11]}, {1, 2, 3})
                self.assertNotIn('_source_reference_components', result[11][0])
                invalid = dict(events, **{})
                invalid[11] = dict(events[11], participants=participants[:1])
                with self.assertRaisesRegex(ValueError, 'Missing or inconsistent'):
                    visibility._source_vehicle_enclosures(certificate,
                        {'capture/recorder_info.txt': recorder}, invalid,
                        {'frames': [{'original_frame': 10}]}, lambda *args: enclosure,
                        inventory, static_actors=(3,))

    def test_probe_checkpoint_resolves_boundary_bracket(self):
        def sample(d):
            return [{'clear': d < 152.4, 'blockers': [] if d < 152.4 else [{'label': 'wall'}]}]
        h = capture.sampled_horizon(sample, 230., 10., .25, checkpoints=[152.4])
        self.assertEqual(h['bracket_m'][1], 152.4)
        v = measured([h])
        v['approaches'][0]['any_sample_clear_at_probe'] = False
        self.assertLess(sight_distance(v)[0], 152.4)

    @unittest.skipUnless(sdk_available(),'Run with the installed CARLA SDK interpreter')
    def test_capture_all_lanes_and_actual_moving_body(self):
        import carla
        from types import SimpleNamespace
        from unittest.mock import patch
        actor = SimpleNamespace(
            get_transform=lambda: carla.Transform(carla.Location(x=20, y=7)),
            bounding_box=carla.BoundingBox(carla.Location(), carla.Vector3D(2, 1, 1)))
        def lane(lid):
            wp = SimpleNamespace(road_id=9, lane_id=lid, s=1000,
                                 transform=carla.Transform(carla.Location(x=20, y=lid*4)))
            def previous(d):
                if d <= 0:raise RuntimeError('distance > 0.0')
                return [SimpleNamespace(road_id=9,lane_id=lid,s=1000-d,transform=carla.Transform(carla.Location(x=20-d,y=lid*4)))]
            wp.previous = previous
            wp.next = lambda d: []
            return wp
        mapping = SimpleNamespace(get_waypoint=lambda *a, **k: lane(-1),
                                  get_waypoint_xodr=lambda road, lid, station: lane(lid),
                                  to_opendrive=lambda: synthetic_lane_topology([-2,-1,1]))
        world = SimpleNamespace()
        # Centre ray becomes blocked beyond 100 m; a corner remains visible.
        def ray(world, actor, eye, point):
            clear = not (eye.x < -80 and point.x == 20 and point.y == 7)
            return {'clear': clear, 'blockers': [] if clear else [{'label': 'wall'}]}
        with patch.object(capture, 'ray_evidence', side_effect=ray):
            v = capture.actor_visibility(world, actor, mapping=mapping,
                                         lane_inventory={9: [-2, -1, 1]}, max_distance_m=230)
        self.assertEqual(v['required_lane_ids'], [-2, -1, 1])
        self.assertEqual(len(v['approaches']), 3)
        self.assertEqual(sight_distance(v)[0], 230)
        self.assertLess(v['approaches'][0]['centre_sight_horizon']['distance_m'], 110)
        self.assertEqual(v['approaches'][0]['any_body_sight_horizon']['bound'], 'at_least')
        actor.get_transform = lambda: carla.Transform(carla.Location(x=25, y=8))
        world.cast_ray = lambda eye, target: []
        moved = capture.actor_visibility(world, actor, mapping=mapping,
                                        lane_inventory={9: [-2, -1, 1]})
        self.assertEqual(moved['ego_body_samples_m'][0], [25, 8, 0])

    @unittest.skipUnless(sdk_available(),'Run with the installed CARLA SDK interpreter')
    def test_distant_probe_branch_preserves_measured_near_horizon(self):
        import carla
        from types import SimpleNamespace
        from unittest.mock import patch
        actor=SimpleNamespace(get_transform=lambda:carla.Transform(),
            bounding_box=carla.BoundingBox(carla.Location(),carla.Vector3D(2,1,1)))
        lane=SimpleNamespace(road_id=9,lane_id=-1,s=1000,transform=carla.Transform())
        lane.previous=lambda d: [] if d>=100 else [SimpleNamespace(
            road_id=9,lane_id=-1,s=1000-d,transform=carla.Transform(carla.Location(x=-d)))]
        lane.next=lambda d: []
        mapping=SimpleNamespace(get_waypoint=lambda *a,**k:lane,
            get_waypoint_xodr=lambda *a:lane,to_opendrive=lambda:synthetic_lane_topology([-1]))
        def ray(world,actor,eye,point):
            clear=eye.x>-10
            return {'clear':clear,'blockers':[] if clear else [{'label':'wall'}]}
        with patch.object(capture,'ray_evidence',side_effect=ray):
            observed=capture.actor_visibility(SimpleNamespace(),actor,mapping=mapping,
                lane_inventory={9:[-1]})
        approach=observed['approaches'][0]
        self.assertIn('probe_unknown_reason',approach)
        self.assertNotIn('any_sample_clear_at_probe',approach)
        self.assertNotIn('unknown_reason',approach)
        value,reason=sight_distance(observed)
        self.assertIsNotNone(value)
        self.assertLess(value,10)
        # An unfinished horizon remains unknown even when the probe error is separate.
        approach['any_body_sight_horizon']={'bound':'route_limit','unknown':True,'distance_m':5}
        self.assertIsNone(sight_distance(observed)[0])

    def test_any_clear_not_centre(self):
        def sample(d):
            return [{'clear': d < 100, 'blockers': [] if d < 100 else [{'label': 'wall'}]},
                    {'clear': d < 175, 'blockers': [] if d < 175 else [{'label': 'wall'}]}]
        h = capture.sampled_horizon(sample, 230, 10, .25)
        self.assertLessEqual(h['bracket_m'][0], 175)
        self.assertGreaterEqual(h['bracket_m'][1], 175)
        self.assertGreater(h['distance_m'], 170)
        self.assertEqual(len(h['blocked_rays']), 2)

    def test_censored_and_missing_route(self):
        h = capture.sampled_horizon(lambda d: [{'clear': True}], 230, 10, .25)
        self.assertEqual(h, {'distance_m': 230, 'bound': 'at_least'})
        h = capture.sampled_horizon(lambda d: None if d >= 20 else [{'clear': True}], 230, 10, .25)
        self.assertTrue(h['unknown']); self.assertEqual(h['distance_m'], 10)

    def test_minimum_uses_clear_side(self):
        v = measured([boundary(160), {'bound': 'at_least', 'distance_m': 230}])
        self.assertEqual(sight_distance(v)[0], 160)

    def test_old_centre_only_capture_unknown(self):
        self.assertIsNone(sight_distance({'approaches': [{'centre_sight_horizon': boundary(160)}]})[0])

    def test_missing_approach_and_route_unknown(self):
        v = measured([boundary(160), boundary(180)])
        v['approaches'].pop()
        self.assertIsNone(sight_distance(v)[0])
        v = measured([{'bound': 'route_limit', 'distance_m': 100, 'unknown': True}])
        self.assertIsNone(sight_distance(v)[0])

    def test_finite_uncertainty_retained_and_short_search_unknown(self):
        self.assertEqual(sight_distance(measured([boundary(152.35)]))[0],152.35)
        self.assertIsNone(sight_distance(measured([{'bound': 'at_least', 'distance_m': 100}]))[0])

    def test_finite_interval_does_not_decide_unknown_probe(self):
        v=measured([{'bound':'first_sampled_occlusion','bracket_m':[129.21875,160.]}])
        v['horizon_tolerance_m']=30.78125
        v['approaches'][0].pop('any_sample_clear_at_probe')
        v['approaches'][0]['probe_unknown_reason']='Saved query has one unresolved sample'
        before=repr(v)
        self.assertEqual(sight_distance(v)[0],129.21875)
        self.assertEqual(repr(v),before)

    def test_conflicting_probe_unknown(self):
        v = measured([boundary(170)])
        v['approaches'][0]['any_sample_clear_at_probe'] = False
        self.assertIsNone(sight_distance(v)[0])

    def test_invalid_measurement_rejected(self):
        with self.assertRaises(ValueError): sight_distance(measured([boundary(float('nan'))]))

    def test_subject_proxy_attaches_only_to_current_occupied_regions(self):
        from shapely.geometry import box
        regions = [{'id': 1, 'kind': 'lane'}, {'id': 2, 'kind': 'roadway'},
                   {'id': 3, 'kind': 'obstruction'}, {'id': 4, 'kind': 'roadway'}]
        polygons = {1: box(0, 0, 10, 10), 2: box(0, 0, 10, 10),
                    3: box(0, 0, 10, 10), 4: box(20, 0, 30, 10)}
        first, mapping = attach_visibility(regions, polygons, box(1, 1, 2, 2), measured([boundary(160)]))
        self.assertEqual(mapping['attached_regions'], [1,2])
        self.assertEqual(mapping['value_m'],160)
        self.assertEqual(first[0]['sight_distance'],160)
        self.assertNotIn('sight_distance',first[2])
        moved=measured([boundary(180)])
        moved['ego_body_samples_m']=[[x+20,y,z] for x,y,z in moved['ego_body_samples_m']]
        second, mapping = attach_visibility(regions, polygons, box(21, 1, 22, 2), moved)
        self.assertEqual(mapping['attached_regions'], [4])
        self.assertEqual(second[3]['sight_distance'],180)
        self.assertNotIn('sight_distance', second[0])
        self.assertTrue(all('sight_distance' not in r for r in regions))

    def test_censored_proxy_retains_lower_bound_without_cutoff(self):
        from shapely.geometry import box
        value=measured([{'bound':'at_least','distance_m':230}])
        regions=[{'id':1,'kind':'roadway'}]
        projected,mapping=attach_visibility(regions,{1:box(0,0,10,10)},box(1,1,2,2),value)
        self.assertEqual(projected[0]['sight_distance'],230)
        self.assertTrue(mapping['search_censored'])
        self.assertEqual(mapping['lower_bound_m'],230)
        self.assertIsNone(mapping['upper_bound_m'])

    def test_stale_body_and_missing_convention_stay_unknown(self):
        from shapely.geometry import box
        value=measured([boundary(160)])
        regions=[{'id':1,'kind':'lane','sight_distance':999}]
        result,mapping=attach_visibility(regions,{1:box(0,0,10,10)},box(5,5,6,6),value)
        self.assertIsNone(mapping['value_m'])
        self.assertNotIn('sight_distance',result[0])
        value.pop('eye_height_m')
        self.assertIsNone(sight_distance(value)[0])

    def test_finite_minimum_is_not_censored_by_a_clear_other_direction(self):
        from shapely.geometry import box
        value = measured([
            {'bound': 'first_sampled_occlusion', 'bracket_m': [9.75, 10.]},
            {'bound': 'at_least', 'distance_m': 230.}])
        result, mapping = attach_visibility(
            [{'id': 1, 'kind': 'roadway'}], {1: box(0, 0, 10, 10)},
            box(1, 1, 2, 2), value)
        self.assertEqual(result[0]['sight_distance'], 9.75)
        self.assertEqual(mapping['upper_bound_m'], 10.)
        self.assertFalse(mapping['search_censored'])

    def test_declared_probe_is_not_hardcoded_to_500_feet(self):
        value=measured([{'bound':'at_least','distance_m':120}]);value['probe_distance_m']=100
        self.assertEqual(sight_distance(value)[0],120)

    def test_reconstruction_rederives_and_is_idempotent(self):
        from traffic_spec_adapter.adapter import repair_scene
        value=measured([boundary(160)])
        scene={'t':0,'subject':1,'users':[{'track':1,'kin':{}}],
               'structures':[{'id':2,'kind':'lane','boundary':[[0,0],[10,0],[10,10],[0,10]]}],'devices':[]}
        packet={'subject_visibility':{'subject':1,'visibility':value,'body_vertices_m':value['ego_body_samples_m'][1:]}}
        changes=repair_scene(scene,set(),packet,{}, {},{(1,0,1):2})
        self.assertEqual(scene['structures'][0]['sight_distance'],160)
        self.assertEqual(changes['projected_measured_sight_distance'],1)
        self.assertFalse(repair_scene(scene,set(),packet,{}, {},{(1,0,1):2}))
        repair_scene(scene,set(),{}, {}, {})
        self.assertNotIn('sight_distance',scene['structures'][0])

    def test_native_map_catches_omitted_approaching_direction(self):
        from shapely.geometry import box
        value=measured([boundary(160)])
        regions=[{'id':1,'kind':'lane'}]
        result,mapping=attach_visibility(regions,{1:box(0,0,10,10)},box(1,1,2,2),value,
                                         {(1,0,1):1,(1,0,-1):2})
        self.assertIsNone(mapping['value_m'])
        self.assertNotIn('sight_distance',result[0])




class VisibilitySourceInventoryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.map=self.root/'road.xodr'
        self.map.write_text('<OpenDRIVE><road id="1"><lanes><laneSection s="0"><left><lane id="1" type="driving"/><lane id="2" type="driving"/><lane id="3" type="shoulder"/></left></laneSection></lanes></road></OpenDRIVE>')

    def inventory(self):
        from traffic_spec_adapter.adapter import _visibility_lane_inventory,sha
        return _visibility_lane_inventory(self.map,sha(self.map))

    def scene_packet(self):
        value=measured([{'bound':'at_least','distance_m':230.}]*2)
        packet={'subject_visibility':{'subject':7,'body_vertices_m':value['ego_body_samples_m'][1:],'visibility':value}}
        scene={'t':0,'subject':7,'users':[],'devices':[],
            'structures':[{'id':10,'kind':'lane','boundary':[[0,0],[3,0],[3,3],[0,3]]}]}
        return scene,packet

    def test_partial_export_binding_does_not_limit_complete_source_scope(self):
        import copy
        from traffic_spec_adapter.adapter import repair_scene
        scene,packet=self.scene_packet();bindings={(1,0,1):10};original=copy.deepcopy(bindings)
        partial=copy.deepcopy(scene);repair_scene(partial,set(),packet,{}, {},bindings)
        self.assertNotIn('sight_distance',partial['structures'][0])
        repair_scene(scene,set(),packet,{}, {},bindings,visibility_native_lanes=self.inventory())
        self.assertEqual(scene['structures'][0]['sight_distance'],230.)
        self.assertEqual(bindings,original)


    @unittest.skipUnless(hasattr(__import__('shapely'),'prepare'),'Retained processing uses the Shapely2 environment')
    def test_reconstruct_forwards_complete_inventory_after_partial_export_match(self):
        import copy,json
        from unittest.mock import patch
        from traffic_spec_adapter import adapter
        root=self.root/'recording';e=root/'evidence';e.mkdir(parents=True)
        road=e/'road.xodr'
        road.write_text('<OpenDRIVE><road id="1" length="100" junction="-1"><link/><planView><geometry s="0" x="0" y="0" hdg="0" length="100"><line/></geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><center><lane id="0" type="none"/></center><right><lane id="1" type="driving"><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane><lane id="2" type="driving"><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>')
        capture=e/'capture';capture.mkdir();events=capture/'evidence.jsonl'
        events.write_text(json.dumps({'recording_time_s':0.,'actor_id':7})+'\n')
        (root/'evidence-checksums.json').write_text(json.dumps({'evidence/road.xodr':adapter.sha(road),'evidence/capture/evidence.jsonl':adapter.sha(events)}))
        scene,packet=self.scene_packet();scene['users']=[{'track':7}];scene['occupies']=[[7,10]]
        trace=root/'trace.json';trace.write_text(json.dumps({'scenes':[scene]}))
        bindings={(1,0,1):10};before=copy.deepcopy(bindings)
        library=Path(adapter.__file__).resolve()
        # Existing module-root library lookup is supplied by the suite runner when
        # testing an external candidate; installed tests use the repository root.
        import os
        library=Path(os.environ.get('TRAFFIC_SPEC_TEST_LIBRARY',str(base/'library')))
        with patch('traffic_spec_adapter.geometry.retained_map',return_value=({},bindings,[],{},[])),patch('traffic_spec_adapter.adapter.source_packets',return_value={0:packet}),patch('traffic_spec_adapter.adapter.validate_scene'),patch('traffic_spec_adapter.native_road_profile.source_surface_certificate',return_value=None):
            adapter.reconstruct(trace,e,library,root/'out.json')
        result=json.loads((root/'out.json').read_text())['scenes'][0]
        self.assertEqual(result['structures'][0]['sight_distance'],230.)
        self.assertEqual(bindings,before)

    def test_incomplete_source_inventory_still_rejected(self):
        from traffic_spec_adapter.adapter import repair_scene
        scene,packet=self.scene_packet()
        repair_scene(scene,set(),packet,{}, {},{(1,0,1):10},visibility_native_lanes={(1,0,1)})
        self.assertNotIn('sight_distance',scene['structures'][0])

    def test_source_inventory_is_not_inferred_from_measurement(self):
        from traffic_spec_adapter.adapter import repair_scene
        scene,packet=self.scene_packet()
        self.map.write_text(self.map.read_text().replace('<lane id="2" type="driving"/>',''))
        repair_scene(scene,set(),packet,{}, {},{(1,0,1):10},visibility_native_lanes=self.inventory())
        self.assertNotIn('sight_distance',scene['structures'][0])

    def test_wrong_map_hash_is_rejected(self):
        from traffic_spec_adapter.adapter import _visibility_lane_inventory,sha
        original=sha(self.map);self.map.write_text(self.map.read_text().replace('id="1"','id="9"',1))
        with self.assertRaisesRegex(ValueError,'map source differs'):_visibility_lane_inventory(self.map,original)

    def test_inventory_preserves_sections_and_excludes_other_lane_kinds(self):
        self.map.write_text(self.map.read_text().replace('</lanes>','<laneSection s="10"><right><lane id="-1" type="driving"/><lane id="-2" type="biking"/></right></laneSection></lanes>'))
        self.assertEqual(self.inventory(),frozenset({(1,0,1),(1,0,2),(1,1,-1)}))

    def test_absent_source_does_not_reuse_partial_bindings(self):
        from traffic_spec_adapter.adapter import repair_scene,_visibility_lane_inventory
        scene,packet=self.scene_packet()
        repair_scene(scene,set(),packet,{}, {},{(1,0,1):10},visibility_native_lanes=_visibility_lane_inventory(None,None))
        self.assertNotIn('sight_distance',scene['structures'][0])

if __name__ == '__main__': unittest.main()


class StaticPropCaptureTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('carla_sgg') and
                         importlib.util.find_spec('carla') and
                         hasattr(importlib.import_module('carla'), 'Vector3D'),
                         'Run with the CARLA SDK and graph generator on PYTHONPATH')
    def test_traffic_prop_geometry_survives_crop_only_when_enabled(self):
        from carla_sgg import sgg
        from types import SimpleNamespace
        from unittest.mock import patch
        from shapely.geometry import box
        generator=object.__new__(sgg.SGG)
        area=box(-25,0,25,50)
        for blueprint in ['static.prop.streetbarrier','static.prop.trafficcone02']:
            actor=SimpleNamespace(type_id=blueprint)
            with patch.object(sgg,'get_actor_transform',return_value=None),patch.object(sgg,'get_actor_bb_matplotlib',return_value=[(70,70),(71,70),(71,71),(70,71)]):
                self.assertFalse(generator.should_consider_actor(None,area,None,actor))
                self.assertTrue(generator.should_consider_actor(None,area,None,actor,True))


class SightDistanceIntegration(unittest.TestCase):
    @unittest.skipUnless(__import__('os').environ.get('SIGHT_DISTANCE_VALIDATOR'),
                         'Set SIGHT_DISTANCE_VALIDATOR to the current full Lean decoder')
    def test_complete_projection_decode_video_and_missing_lane(self):
        import json, os, tempfile, copy, xml.etree.ElementTree as ET
        from unittest.mock import patch
        from worker_exchange.fixture_generator import generate
        from worker_exchange.common import read, write, sha
        from worker_exchange.runtime_cli import process, render
        from worker_exchange.media import audit
        library = base/'library' if (base/'library').is_dir() else base/'library'
        fixture = base/'fixtures/example.json' if (base/'fixtures/example.json').is_file() else base/'worker_exchange/templates/fixture-example.json'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';spec=read(fixture);generate(spec,attempt)
            events=[json.loads(line) for line in (attempt/'capture/evidence.jsonl').read_text().splitlines()]
            xml=ET.parse(attempt/'road.xodr')
            for event in events:
                vertices=event['ego']['body_vertices_m']
                road=event['world']['road_projection']['road_id']
                lanes=sorted({int(lane.get('id')) for lane in xml.findall("./road[@id='%s']/lanes/laneSection/*/lane"%road) if lane.get('type')=='driving'})
                v=measured([boundary(160) if index==0 else {'bound':'at_least','distance_m':230} for index in range(len(lanes))])
                v['required_lane_ids']=lanes;v['ego_projection']={'road_id':road}
                v['ego_body_samples_m']=[[sum(p[i] for p in vertices)/len(vertices) for i in range(3)],*vertices]
                for lane,approach in zip(lanes,v['approaches']):approach['lane_id']=lane
                event['visibility']=v
            (attempt/'capture/evidence.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            write(attempt/'config.json',{'required_atoms':['st.sight_distance']})
            capture_manifest=read(attempt/'capture/manifest.json')
            capture_manifest['required_observations']=['st.sight_distance']
            write(attempt/'capture/manifest.json',capture_manifest)
            write(attempt/'result.json',{'video_references':[spec['videos'][0]['path']]})
            collection=root/'collection';initial=collection/'inputs/shared/manifest.json'
            write(initial,{'source':'initial-diagnostic-profile','atoms':{'st.sight_distance':'absent'}})
            old_hash=sha(initial)
            with patch('pipeline_paths.OUTPUT_ROOT',collection):
                output=root/'converted';process(attempt,output,library,os.environ['SIGHT_DISTANCE_VALIDATOR'],diagnostic_fixture=True)
                trace=read(output/'trace.json')
                self.assertEqual(len(trace['scenes']),len(events))
                for scene in trace['scenes']:
                    values=[r['sight_distance'] for r in scene['structures'] if 'sight_distance' in r]
                    self.assertTrue(values);self.assertEqual(set(values),{160})
                report=read(output/'adapter_report.json')
                self.assertTrue(report['required_measurements_complete'])
                self.assertTrue(report['decoder_validation']['passed'])
                supplement=[json.loads(line) for line in (output/'supplementary_evidence.jsonl').read_text().splitlines()]
                mapping=supplement[0]['visibility_mapping']
                self.assertFalse(mapping['search_censored'])
                self.assertEqual(mapping['lower_bound_m'],160)
                self.assertEqual(mapping['upper_bound_m'],160.125)
                self.assertEqual(sha(initial),old_hash)
                self.assertIn('/manifests/',str((output/'manifest.json').resolve()))
                video=render(attempt,output,{'case_id':'sight-distance-diagnostic','target_law_id':None})
                self.assertTrue(audit(video['video'],len(events))['passed'])
                events[0]['visibility']['approaches'].pop()
                (attempt/'capture/evidence.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
                with self.assertRaisesRegex(ValueError,'Mandatory observation coverage incomplete'):
                    process(attempt,root/'missing-lane',library,os.environ['SIGHT_DISTANCE_VALIDATOR'],diagnostic_fixture=True)
