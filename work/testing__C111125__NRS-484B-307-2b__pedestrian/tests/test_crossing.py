import hashlib
import importlib.util
import json
import subprocess
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
capture_module = module('native_capture')
media_audit = module('saved_media_audit')
delivery = module('delivery_audit')


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


if __name__ == '__main__':
    unittest.main()
