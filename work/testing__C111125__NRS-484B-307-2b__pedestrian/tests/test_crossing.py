import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


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
capture_module = module('native_capture')
media_audit = module('saved_media_audit')
delivery = module('delivery_audit')
owned = module('owned_runner')
graph_sink = module('pedestrian_graph_sink')
publication = module('native_publication')
finalizer = module('saved_finalizer')


class CrossingTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111125-crossing-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.refs = [
            self.write('map.json', json.dumps({'public_highway':True, 'highway_polygon_xy':[[0,0],[10,0],[10,10],[0,10]],
                                               'crosswalk_polygon_xy':[[0,4],[10,4],[10,6],[0,6]],
                                               'crosswalk_kind':'marked', 'crosswalk_qualifies':True})),
            self.write('head.json', json.dumps({'official':True,'control':'traffic_light','head_id':'head1','pedestrian_faces_head':True})),
            self.write('devices.json', json.dumps({'other_device_id':'ped1','inventory_complete':True,
                'route_applicability':{'route_id':'route1','device_id':'ped1','applies':True,
                    'law_refs':['NRS-484B-283-1d1', 'NRS-484B-283-1d4'],
                    'review_basis':'test-only original route inventory'}})),
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
            'pedestrian_route_id': 'route1',
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

    def test_device_mode_and_countdown_retained_from_original(self):
        self.events('DONT_WALK')
        rows = json.loads((self.root / 'frames.json').read_text())
        for row in rows:
            row['other_device_mode'] = 'flashing_countdown'
            row['other_device_countdown'] = 8
        ref = self.write('frames.json', json.dumps(rows))
        facts = crossing.measure(self.site, self.root, ref)
        self.assertEqual(facts['first_highway_entry']['other_device_countdown'], 8)
        rows[1]['other_device_countdown'] = None
        ref = self.write('frames.json', json.dumps(rows))
        with self.assertRaisesRegex(ValueError, 'countdown lacks observed'):
            crossing.measure(self.site, self.root, ref)

    def test_entry_transition_preserves_before_and_at_device_modes(self):
        self.events('DONT_WALK')
        rows = json.loads((self.root / 'frames.json').read_text())
        rows[0]['other_device_mode'] = 'flashing_countdown'
        rows[0]['other_device_countdown'] = 8
        rows[1]['other_device_mode'] = 'steady'
        rows[1]['other_device_countdown'] = None
        facts = crossing.measure(self.site, self.root, self.write('frames.json', json.dumps(rows)))
        transition = facts['entry_transition']
        self.assertEqual((transition['before_frame'], transition['entry_frame']), (0, 1))
        self.assertEqual((transition['before_device_mode'], transition['entry_device_mode']),
                         ('flashing_countdown', 'steady'))
        self.assertTrue(transition['entry_green_alone'])
        self.assertTrue(transition['entered_within_crosswalk'])
        self.assertIsNone(facts['legal_verdict'])

    def test_no_highway_entry_has_no_entry_transition(self):
        self.events()
        rows = json.loads((self.root / 'frames.json').read_text())
        rows[1]['pedestrian_xy'] = [-1, 5]
        facts = crossing.measure(self.site, self.root, self.write('frames.json', json.dumps(rows)))
        self.assertIsNone(facts['entry_transition'])

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

    def test_each_device_alternative_comparison_requires_original_timeline(self):
        common = {key: 'same' for key in (
            'map_source_sha256', 'signal_source_sha256',
            'device_inventory_source_sha256', 'highway_polygon_source_sha256',
            'camera_profile_sha256')}
        common.update(duration_frames=4, crosswalk_kind='marked',
                      green_alone_frames=4, source_bound=True)
        baseline = {**common, 'case_suffix': 'marked_cross',
                    'first_highway_entry': {
                        'other_device_indication': 'none', 'in_crosswalk': True}}
        for comparison_id, (suffix, mode, enters) in comparison.DEVICE_ALTERNATIVES.items():
            timeline = {'format': 'c111125-saved-device-timeline-v1',
                        'original_first_frame': 0, 'original_last_frame': 3,
                        'entry_frame': 1 if enters else None,
                        'entry_device_mode': mode if enters else None,
                        'entry_within_crosswalk': True if enters else None,
                        'clearance_frame': 2 if enters else None,
                        'cleared_before_countdown_zero_observed': True,
                        'cleared_before_steady_observed': True,
                        'first_steady_frame': 3,
                        'legal_verdict': None, 'physical_acceptance': False}
            alternative = {**common, 'case_suffix': suffix,
                           'first_highway_entry': {'in_crosswalk': True} if enters else None,
                           'device_indication_while_waiting': 'DONT_WALK',
                           'device_timeline': timeline}
            self.assertFalse(comparison.audit_pair(comparison_id, baseline, alternative)['physical_acceptance'])
            alternative['source_bound'] = False
            with self.assertRaisesRegex(comparison.ComparisonError, 'source binding'):
                comparison.audit_pair(comparison_id, baseline, alternative)
            alternative['source_bound'] = True
            alternative['device_timeline'] = {**timeline, 'original_last_frame': 2}
            with self.assertRaisesRegex(comparison.ComparisonError, 'frame span'):
                comparison.audit_pair(comparison_id, baseline, alternative)

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

    def native_fakes(self):
        class Location:
            def __init__(self, x, y, z=0):
                self.x, self.y, self.z = x, y, z
        class Actor:
            id = 42
            type_id = 'walker.pedestrian.0001'
            def __init__(self):
                self.location = Location(-2, 5)
                self.command = {'direction': (0, 0, 0), 'speed': 0}
            def get_location(self):
                return self.location
            def apply_control(self, command):
                self.command = command
        class World:
            def __init__(self, actor):
                self.actor = actor
                self.frame = 0
                self.gap = False
            def get_snapshot(self):
                from types import SimpleNamespace
                return SimpleNamespace(frame=self.frame,
                    timestamp=SimpleNamespace(elapsed_seconds=self.frame * .05))
            def tick(self):
                self.frame += 2 if self.gap else 1
                direction = self.actor.command['direction']
                speed = self.actor.command['speed']
                self.actor.location.x += direction[0] * speed * .05
                self.actor.location.y += direction[1] * speed * .05
                return self.frame
        actor = Actor()
        world = World(actor)
        head = lambda identity: {'head_id': identity, 'pedestrian_faces_head': True,
                                 'lit_aspects': ['circular_green']}
        device = lambda identity: {'device_id': identity, 'indication': 'none',
                                   'mode': 'absent', 'countdown': None}
        return actor, world, head, device

    def test_native_capture_original_motion_and_waypoint_advance(self):
        actor, world, head, device = self.native_fakes()
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            self.root / 'attempt', ticks=90)
        self.assertEqual(receipt['frame_count'], 91)
        self.assertEqual(receipt['first_highway_entry_frame'], 34)
        self.assertGreater(actor.location.x, 2.5)
        self.assertEqual(actor.command['speed'], 0)
        saved = self.root / 'attempt' / receipt['original_frames']['path']
        self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),
                         receipt['original_frames']['sha256'])
        rows = json.loads(saved.read_text())
        self.assertEqual(rows[0]['actor_id'], 42)
        self.assertEqual(rows[-1]['frame'], 90)

    def test_reviewed_owner_runs_full_900_frame_wait_capture_and_rejects_fixture(self):
        from io import BytesIO
        from types import SimpleNamespace
        from PIL import Image
        actor, world, head, device = self.native_fakes()
        actor.get_transform = lambda: object()
        actor.destroy = lambda: setattr(actor, 'destroyed', True)
        world.try_spawn_actor = lambda blueprint, transform: actor
        class Library:
            def find(self, blueprint):
                return blueprint
        dimensions = {'overview': (1920, 1080),
                      'approach': (1280, 720),
                      'reference_corner': (1280, 720),
                      'driver_reference': (1280, 720)}
        pngs = {}
        for name, size in dimensions.items():
            stream = BytesIO()
            Image.new('RGB', size, (10, 20, 30)).save(stream, format='PNG')
            pngs[name] = stream.getvalue()
        cameras = {name: (lambda frame, data=pngs[name]:
                          {'frame': frame, 'png_bytes': data})
                   for name in capture_module.CAMERAS}
        class FrameSink:
            def __init__(self):
                self.frames = []
                self.closed = None
            def capture(self, row):
                self.frames.append(row['frame'])
            def close(self, confirmed=True):
                self.closed = confirmed
        sink = FrameSink()
        session = SimpleNamespace(world=world, blueprint_library=Library(),
            transform_factory=lambda *xyz: xyz, head_reader=head, device_reader=device,
            control_factory=lambda **kw: kw, vector_factory=lambda *xyz: xyz,
            camera_readers=cameras, frame_sink=sink)
        case_id = capture_module.ASSIGNMENT + '__other_device_stop'
        attempt = self.root / 'full-attempt'
        attempt.mkdir()
        (attempt / 'config.json').write_text(json.dumps({'selected_case_id': case_id}))
        (attempt / 'construction.json').write_text('{}')
        self.site.update(diagnostic_fixture=True, reviewed_original_site=True,
                         review_source_id='test-only')
        site_path = self.root / 'site.json'
        site_path.write_text(json.dumps(self.site))
        with self.assertRaisesRegex(ValueError, 'reviewed original'):
            owned.capture_reviewed(session, site_path, case_id, attempt,
                camera_dimensions=dimensions)
        self.site['diagnostic_fixture'] = False
        site_path.write_text(json.dumps(self.site))
        receipt = owned.capture_reviewed(session, site_path, case_id, attempt,
            camera_dimensions=dimensions,
            publisher=lambda output, exact_case: {'case_id': exact_case,
                                                   'scope': 'fake-publisher-only'})
        self.assertEqual(receipt['frame_count'], 900)
        self.assertEqual(receipt['last_frame'], 899)
        self.assertEqual(sink.frames, list(range(900)))
        self.assertTrue(sink.closed)
        self.assertTrue(actor.destroyed)
        self.assertEqual(media_audit.audit(attempt)['decoded_images'], 3600)
        self.assertEqual(receipt['reviewed_site_source']['sha256'],
                         hashlib.sha256((attempt / 'site-source.json').read_bytes()).hexdigest())
        reviewed_result = delivery.audit(attempt, receipt['reviewed_site_source'],
                                       'other_device_stop', require_reviewed=True)
        self.assertEqual(reviewed_result['decoded_images'], 3600)
        from production_delivery_audit import verify as verify_production
        production_result = verify_production(case_id, attempt)
        self.assertEqual(production_result['saved_protocol']['decoded_images'], 3600)
        self.assertFalse(production_result['physical_acceptance'])
        selected = json.loads((ROOT / 'cases/other_device_stop/delivery-construction.draft.json').read_text())
        selected_config = json.loads(next(item['content'] for item in selected['files']
                                         if item['path'] == 'config.json'))
        selected_config['case']['diagnostic_only'] = False
        (attempt / 'config.json').write_text(json.dumps(selected_config))
        (attempt / 'construction.json').write_text(json.dumps(selected))
        (attempt / 'runner.py').write_text('pass\n')
        originals = json.loads((attempt / 'original-frames.json').read_text())
        native = attempt / 'capture/native'
        graph_dir = native / 'graphs/base'
        graph_dir.mkdir(parents=True)
        graph_index = []
        evidence = []
        trace = []
        for row in originals:
            frame = row['frame']
            graph_ref = f'graphs/base/{frame:08d}.adapter.json'
            x, y = row['pedestrian_xy']
            vertices = [[vx, vy, z] for vx, vy in
                        ((x - .2, y - .2), (x + .2, y - .2),
                         (x + .2, y + .2), (x - .2, y + .2))
                        for z in (0, 1.8)]
            observed = {'frame': frame, 'time_s': row['elapsed_seconds'],
                        'map_context': {'declared_public_way_road_ids': []},
                        'participants': [{'actor_id': 42,
                                          'blueprint': actor.type_id,
                                          'position_m': [x, y, 0],
                                          'heading_deg': 0,
                                          'speed_mps': 0,
                                          'velocity_mps': [0, 0, 0],
                                          'body_vertices_m': vertices}]}
            (native / graph_ref).write_text(json.dumps({
                'format': 'native-adapter-graph-v1',
                'multigraph': False,
                'metadata': {'frame': frame,
                             'observed_evidence': observed},
                'nodes': [], 'edges': []}))
            graph_index.append({'frame': frame, 'simulation_time': row['elapsed_seconds'],
                                'adapter_graph': graph_ref})
            evidence.append({'actor_id': 42, 'original_frame': frame,
                             'replay_frame': frame,
                             'recording_time_s': row['elapsed_seconds'],
                             'replay_simulation_time_s': row['elapsed_seconds'],
                             'ego': {'position_m': [x, y, 0],
                                     'heading_deg': 0, 'speed_mps': 0,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': vertices},
                             'original_observations': observed,
                             'world': {'weather': {}}})
            trace.append({'frame': frame, 'time_s': row['elapsed_seconds'],
                          'position': {'x': x, 'y': y, 'z': 0},
                          'position_m': [x, y, 0], 'actor_id': 42,
                          'heading_deg': 0,
                          'speed_mps': 0, 'speed_mph': 0,
                          'velocity_mps': [0, 0, 0], 'control': {}})
        (native / 'frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in graph_index))
        (attempt / 'capture/evidence.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in evidence))
        (attempt / 'capture/recorder_info.txt').write_text(
            'Create 42: walker.pedestrian.0001 (synthetic diagnostic)\n')
        (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
        shutil.copyfile(ROOT / 'diagnostic-road.xodr', attempt / 'road.xodr')
        (attempt / 'capture/manifest.json').write_text(json.dumps({
            'case_id': case_id, 'frames': 900, 'extraction_confirmed': True,
            'status': 'diagnostic_only',
            'acquisition': 'synthetic_diagnostic_fixture',
            'diagnostic_fixture': True,
            'sources': {
                name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                for name in ('road.xodr', 'trace.jsonl')}}))
        (attempt / 'fixture-provenance.json').write_text(json.dumps({
            'diagnostic_fixture': True,
            'scope': 'CPU fake Native publication test; no physical site claim'}))
        sys.path.insert(0, str(ROOT.parents[1] / 'runtime/scenario_pipeline'))
        missing_graph = graph_dir / '00000007.adapter.json'
        graph_bytes = missing_graph.read_bytes()
        missing_graph.unlink()
        with self.assertRaisesRegex(ValueError, 'graph source missing'):
            publication.publish_original(attempt, case_id)
        self.assertFalse((attempt / 'result.json').exists())
        missing_graph.write_bytes(graph_bytes)
        published = publication.publish_original(attempt, case_id)
        self.assertEqual(published['frames'], 900)
        self.assertTrue((attempt / 'result.json').is_file())
        self.assertTrue(json.loads((attempt / 'result.json').read_text())['diagnostic_fixture'])
        with self.assertRaisesRegex(ValueError, 'restoration receipt required'):
            owned.seal_after_restoration(attempt, {'restored': False})
        seal = owned.seal_after_restoration(attempt, {
            'restored': True, 'source': 'CPU fake operator restoration only'})
        self.assertEqual(seal['events'], [
            'capture_finished', 'encoders_closed', 'restoration_verified'])
        stage = self.root / 'saved-stage'
        shutil.copytree(attempt, stage)
        (stage / 'result.json').unlink()
        shutil.rmtree(stage / 'channels')
        saved_report, saved_result = finalizer.analyze_original(stage, case_id)
        self.assertTrue(saved_report['analysis_complete'])
        self.assertTrue(saved_result['diagnostic_fixture'])
        self.assertEqual(saved_report['device_timeline']['entry_frame'], None)
        from worker_exchange import saved_processing
        native_exit = saved_processing.record_native_exit(attempt)
        self.assertEqual(native_exit['event'], 'native_exit')
        owner_receipt = self.root / 'owner-release.json'
        saved_processing.acknowledge_owner_release(attempt, owner_receipt, True)
        processed = saved_processing.run(
            ROOT / 'execution-manifest.draft.json', case_id, attempt,
            self.root / 'process-output', ROOT.parents[1] / 'runtime/library',
            ROOT.parents[1] / '.runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck',
            owner_receipt=owner_receipt)
        self.assertTrue(processed['recorded_only'])
        self.assertTrue(processed['originals_preserved'])
        self.assertTrue(processed['timestamp_joins']['passed'])
        self.assertFalse(processed['missing_evidence'])
        changed = dict(receipt)
        changed.pop('reviewed_site_source')
        (attempt / 'capture-receipt.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'reviewed original site source missing'):
            delivery.audit(attempt, receipt['reviewed_site_source'],
                           'other_device_stop', require_reviewed=True)

    def test_original_frame_sink_failure_cannot_publish_complete_capture(self):
        actor, world, head, device = self.native_fakes()
        class FailingSink:
            closed = None
            def capture(self, row):
                if row['frame'] == 2:
                    raise ValueError('original graph source failed')
            def close(self, confirmed=True):
                self.closed = confirmed
        sink = FailingSink()
        attempt = self.root / 'sink-failure'
        with self.assertRaisesRegex(ValueError, 'original graph source failed'):
            capture_module.capture(world, actor, self.site, self.root,
                'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
                attempt, ticks=3, frame_sink=sink)
        self.assertFalse(sink.closed)
        self.assertFalse((attempt / 'capture-receipt.json').exists())

    def test_pedestrian_graph_sink_retains_walker_control_without_vehicle_pedals(self):
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch
        actor, world, _, _ = self.native_fakes()
        actor.get_transform = lambda: SimpleNamespace(
            location=SimpleNamespace(x=-2, y=5, z=0),
            rotation=SimpleNamespace(yaw=0))
        actor.get_velocity = lambda: SimpleNamespace(x=0, y=0, z=0)
        actor.get_control = lambda: SimpleNamespace(
            direction=SimpleNamespace(x=1, y=0, z=0), speed=1.2, jump=False)
        road = SimpleNamespace(name='fake-road', to_opendrive=lambda: '<OpenDRIVE/>')
        world.get_map = lambda: road
        class Client:
            def get_world(self):
                return world
            def start_recorder(self, path, additional):
                Path(path).write_text('diagnostic recorder')
            def stop_recorder(self):
                pass
            def show_recorder_file_info(self, path, verbose):
                return 'diagnostic recorder info'
        collector_module = ModuleType('scene_graph_collector')
        class Collector:
            def __init__(self, client, ego_id, output_dir, **kwargs):
                Path(output_dir).mkdir()
            def capture(self, frame, control, observed_evidence):
                self.control = control
                return {'simulation_time': frame * .05}
            def close(self):
                pass
        collector_module.SceneGraphCollector = Collector
        observation_module = ModuleType('original_observations')
        observation_module.observe = lambda native_world, native_actor, frame, time: {
            'participants': [{'actor_id': actor.id, 'blueprint': actor.type_id,
                              'position_m': [-2, 5, 0], 'heading_deg': 0,
                              'speed_mps': 0, 'body_vertices_m': [[-2, 5, 0]]}]}
        with patch.dict(sys.modules, {'scene_graph_collector': collector_module,
                                      'original_observations': observation_module}):
            sink = graph_sink.PedestrianGraphSink(Client(), actor,
                                                  self.root / 'graph-sink',
                                                  capture_module.ASSIGNMENT + '__marked_cross')
            sink.capture({'frame': 0, 'elapsed_seconds': 0,
                          'official_signal_head_id': 'head1',
                          'lit_aspects': ['circular_green'],
                          'other_device_id': 'ped1', 'other_device_mode': 'absent'})
            sink.close()
        trace = json.loads((self.root / 'graph-sink/trace.jsonl').read_text())
        self.assertEqual(trace['control']['walker']['speed'], 1.2)
        self.assertNotIn('throttle', trace['control'])
        manifest = json.loads((self.root / 'graph-sink/capture/manifest.json').read_text())
        self.assertFalse(manifest['extraction_confirmed'])

    def test_native_capture_wait_and_frame_gap_rejection(self):
        actor, world, head, device = self.native_fakes()
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'other_device_stop', head, device, lambda **kw: kw, lambda *xyz: xyz,
            self.root / 'wait-attempt', ticks=3)
        self.assertIsNone(receipt['first_highway_entry_frame'])
        self.assertEqual(actor.location.x, -2)
        actor, world, head, device = self.native_fakes()
        world.gap = True
        with self.assertRaisesRegex(ValueError, 'frame gap'):
            capture_module.capture(world, actor, self.site, self.root,
                'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
                self.root / 'gap-attempt', ticks=2)
        self.assertEqual(actor.command['speed'], 0)
        self.assertFalse((self.root / 'gap-attempt' / 'capture-receipt.json').exists())

    def test_native_capture_rejects_unbound_signal(self):
        actor, world, _, device = self.native_fakes()
        bad_head = lambda identity: {'head_id': 'unbound',
            'pedestrian_faces_head': True, 'lit_aspects': ['circular_green']}
        with self.assertRaisesRegex(ValueError, 'signal head mismatch'):
            capture_module.capture(world, actor, self.site, self.root,
                'marked_cross', bad_head, device, lambda **kw: kw,
                lambda *xyz: xyz, self.root / 'signal-attempt', ticks=2)
        self.assertEqual(actor.command['speed'], 0)

    def test_saved_measurement_requires_matching_native_receipt(self):
        actor, world, head, device = self.native_fakes()
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            self.root, ticks=40)
        site_ref = self.write('site.json', json.dumps(self.site))
        events_ref = receipt['original_frames']
        receipt_ref = {'path': 'capture-receipt.json',
            'sha256': hashlib.sha256((self.root / 'capture-receipt.json').read_bytes()).hexdigest()}
        result = measurement.build_sealed(site_ref, events_ref, receipt_ref, self.root)
        self.assertEqual(result['facts']['first_highway_entry']['frame'], 34)
        self.assertEqual(result['native_capture_receipt_source'], receipt_ref)
        receipt['frame_count'] += 1
        receipt_ref = self.write('capture-receipt.json', json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'frame count mismatch'):
            measurement.build_sealed(site_ref, events_ref, receipt_ref, self.root)

    def test_original_four_camera_capture_and_full_pixel_audit(self):
        from io import BytesIO
        from PIL import Image
        image = Image.new('RGB', (8, 6), 'green')
        stream = BytesIO()
        image.save(stream, format='PNG')
        png = stream.getvalue()
        readers = {name: (lambda frame: {'frame': frame, 'png_bytes': png})
                   for name in capture_module.CAMERAS}
        dimensions = {name: (8, 6) for name in capture_module.CAMERAS}
        actor, world, head, device = self.native_fakes()
        attempt = self.root / 'four-cameras'
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            attempt, ticks=4, camera_readers=readers, camera_dimensions=dimensions)
        self.assertTrue(receipt['camera_capture_complete'])
        self.assertEqual(media_audit.audit(attempt)['decoded_images'], 20)
        self.assertFalse(media_audit.audit(attempt)['physical_acceptance'])
        archive = attempt / 'overview.png.zip'
        archive.write_bytes(archive.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            media_audit.audit(attempt)

    def test_original_camera_frame_mismatch_and_diagnostic_rejection(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 6)).save(stream, format='PNG')
        png = stream.getvalue()
        readers = {name: (lambda frame: {'frame': frame, 'png_bytes': png})
                   for name in capture_module.CAMERAS}
        readers['approach'] = lambda frame: {'frame': frame + 1, 'png_bytes': png}
        actor, world, head, device = self.native_fakes()
        attempt = self.root / 'camera-failure'
        with self.assertRaisesRegex(ValueError, 'camera frame identity mismatch'):
            capture_module.capture(world, actor, self.site, self.root,
                'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
                attempt, ticks=2, camera_readers=readers,
                camera_dimensions={name: (8, 6) for name in capture_module.CAMERAS})
        self.assertEqual(actor.command['speed'], 0)
        self.assertFalse((attempt / 'capture-receipt.json').exists())
        self.assertFalse((attempt / 'overview.png.zip').exists())
        actor, world, head, device = self.native_fakes()
        diagnostic = self.root / 'diagnostic-only'
        capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            diagnostic, ticks=2)
        with self.assertRaisesRegex(ValueError, 'four-camera capture missing'):
            media_audit.audit(diagnostic)

    def test_saved_camera_audit_rechecks_original_time_after_rehash(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 6)).save(stream, format='PNG')
        png = stream.getvalue()
        readers = {name: (lambda frame: {'frame': frame, 'png_bytes': png})
                   for name in capture_module.CAMERAS}
        actor, world, head, device = self.native_fakes()
        attempt = self.root / 'time-gap'
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            attempt, ticks=3, camera_readers=readers,
            camera_dimensions={name: (8, 6) for name in capture_module.CAMERAS})
        self.assertEqual(media_audit.audit(attempt)['decoded_images'], 16)
        receipt['fps'] = 10
        (attempt / 'capture-receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'capture rate mismatch'):
            media_audit.audit(attempt)
        receipt['fps'] = 20
        frames = attempt / 'original-frames.json'
        rows = json.loads(frames.read_text())
        rows[2]['elapsed_seconds'] += 0.1
        frames.write_text(json.dumps(rows))
        receipt['original_frames']['sha256'] = hashlib.sha256(frames.read_bytes()).hexdigest()
        (attempt / 'capture-receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, '20 Hz frame time gap'):
            media_audit.audit(attempt)

    def test_delivery_protocol_joins_original_clearance_and_pixels(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 6)).save(stream, format='PNG')
        png = stream.getvalue()
        readers = {name: (lambda frame: {'frame': frame, 'png_bytes': png})
                   for name in capture_module.CAMERAS}
        self.write('site.json', json.dumps(self.site))
        site_ref = {'path': 'site.json',
                    'sha256': hashlib.sha256((self.root / 'site.json').read_bytes()).hexdigest()}
        actor, world, head, device = self.native_fakes()
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'marked_cross', head, device, lambda **kw: kw, lambda *xyz: xyz,
            self.root, ticks=240, camera_readers=readers,
            camera_dimensions={name: (8, 6) for name in capture_module.CAMERAS})
        result = delivery.audit(self.root, site_ref, 'marked_cross')
        self.assertTrue(result['source_join_passed'])
        self.assertEqual(result['decoded_images'], 964)
        self.assertFalse(result['physical_acceptance'])
        (self.root / 'site-ref.json').write_text(json.dumps(site_ref))
        output = self.root / 'delivery-protocol.json'
        completed = subprocess.run([sys.executable, str(ROOT / 'delivery_audit.py'),
            '--attempt-root', str(self.root), '--site-ref', str(self.root / 'site-ref.json'),
            '--case-suffix', 'marked_cross', '--output', str(output)],
            capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text())['decoded_images'], 964)
        with self.assertRaisesRegex(ValueError, 'case mismatch'):
            delivery.audit(self.root, site_ref, 'unmarked_cross')
        frame_path = self.root / receipt['original_frames']['path']
        rows = json.loads(frame_path.read_text())
        for row in rows:
            if row['pedestrian_xy'][0] > 9.8:
                row['pedestrian_xy'][0] = 9.8
        frame_path.write_text(json.dumps(rows))
        receipt['original_frames']['sha256'] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        (self.root / 'capture-receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'clearance missing'):
            delivery.audit(self.root, site_ref, 'marked_cross')

    def test_countdown_clearance_uses_original_frames_and_rejects_early_zero(self):
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (8, 6)).save(stream, format='PNG')
        png = stream.getvalue()
        readers = {name: (lambda frame: {'frame': frame, 'png_bytes': png})
                   for name in capture_module.CAMERAS}
        self.write('site.json', json.dumps(self.site))
        site_ref = {'path': 'site.json',
                    'sha256': hashlib.sha256((self.root / 'site.json').read_bytes()).hexdigest()}
        actor, world, head, _ = self.native_fakes()
        def device(identity):
            return {'device_id': identity, 'indication': 'DONT_WALK',
                    'mode': 'flashing_countdown', 'countdown': max(230 - world.frame, 0)}
        receipt = capture_module.capture(world, actor, self.site, self.root,
            'flashing_countdown_cross', head, device, lambda **kw: kw,
            lambda *xyz: xyz, self.root, ticks=240, camera_readers=readers,
            camera_dimensions={name: (8, 6) for name in capture_module.CAMERAS})
        result = delivery.audit(self.root, site_ref, 'flashing_countdown_cross')
        self.assertTrue(result['device_timeline']['cleared_before_countdown_zero_observed'])
        self.assertIsNone(result['legal_verdict'])
        frame_path = self.root / receipt['original_frames']['path']
        rows = json.loads(frame_path.read_text())
        for row in rows:
            row['other_device_countdown'] = max(100 - row['frame'], 0)
        frame_path.write_text(json.dumps(rows))
        receipt['original_frames']['sha256'] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
        (self.root / 'capture-receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'clearance before zero not observed'):
            delivery.audit(self.root, site_ref, 'flashing_countdown_cross')


if __name__ == '__main__':
    unittest.main()
