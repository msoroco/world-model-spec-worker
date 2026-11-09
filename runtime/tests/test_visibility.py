"""Any-body measurement, censoring, coverage and subject-relative attachment."""
import importlib.util
import unittest
from pathlib import Path
from traffic_spec_adapter.visibility import sight_distance, attach_visibility, CONVENTION

base = Path(__file__).resolve().parents[1]
path = (base/'python/carla_sgg/law_evidence.py' if (base/'python').is_dir() else
        base.parent/'third_party/carla_scene_graphs/carla_sgg/law_evidence.py')
spec = importlib.util.spec_from_file_location('visibility_capture', path)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


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
            wp = SimpleNamespace(road_id=9, lane_id=lid, s=20,
                                 transform=carla.Transform(carla.Location(x=20, y=lid*4)))
            def previous(d):
                if d <= 0:raise RuntimeError('distance > 0.0')
                return [SimpleNamespace(transform=carla.Transform(carla.Location(x=20-d,y=lid*4)))]
            wp.previous = previous
            return wp
        mapping = SimpleNamespace(get_waypoint=lambda *a, **k: lane(-1),
                                  get_waypoint_xodr=lambda road, lid, station: lane(lid))
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

    def test_threshold_uncertainty_and_short_search_unknown(self):
        self.assertIsNone(sight_distance(measured([boundary(152.35)]))[0])
        self.assertIsNone(sight_distance(measured([{'bound': 'at_least', 'distance_m': 100}]))[0])

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


if __name__ == '__main__': unittest.main()


class StaticPropCaptureTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('carla') and importlib.util.find_spec('carla_sgg'),'Run with CARLA SDK and graph generator on PYTHONPATH')
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
        library = base/'library' if (base/'library').is_dir() else base.parent/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'
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
            write(attempt/'result.json',{'video_references':['raw.mkv']})
            collection=root/'collection';initial=collection/'inputs/shared/manifest.json'
            write(initial,{'source':'initial-diagnostic-profile','atoms':{'st.sight_distance':'absent'}})
            old_hash=sha(initial)
            with patch('pipeline_paths.OUTPUT_ROOT',collection):
                output=root/'converted';process(attempt,output,library,os.environ['SIGHT_DISTANCE_VALIDATOR'])
                trace=read(output/'trace.json')
                self.assertEqual(len(trace['scenes']),len(events))
                for scene in trace['scenes']:
                    values=[r['sight_distance'] for r in scene['structures'] if 'sight_distance' in r]
                    self.assertTrue(values);self.assertEqual(set(values),{160})
                report=read(output/'adapter_report.json')
                self.assertTrue(report['required_measurements_complete'])
                self.assertTrue(report['decoder_validation']['passed'])
                supplement=[json.loads(line) for line in (output/'supplementary_evidence.jsonl').read_text().splitlines()]
                self.assertTrue(supplement[0]['visibility_mapping']['search_censored'])
                self.assertEqual(sha(initial),old_hash)
                self.assertIn('/manifests/',str((output/'manifest.json').resolve()))
                video=render(attempt,output,{'case_id':'sight-distance-diagnostic','target_law_id':None})
                self.assertTrue(audit(video['video'],len(events))['passed'])
                events[0]['visibility']['approaches'].pop()
                (attempt/'capture/evidence.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
                with self.assertRaisesRegex(ValueError,'Mandatory observation coverage incomplete'):
                    process(attempt,root/'missing-lane',library,os.environ['SIGHT_DISTANCE_VALIDATOR'])
