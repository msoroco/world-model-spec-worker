import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from overpass_source import (CASES, FRAMES, audit_pair, audit_saved, measure_original,
                             native_sample, request_controls, sha, spawn_pair,
                             validate_case, validate_map)
from native_capture import CAMERA_SPECS, camera_placements
from site_review import inspect as inspect_site

ROOT = Path(__file__).resolve().parents[1]


class FakeActor:
    def __init__(self, xyz, ident):
        self.xyz = xyz
        self.id = ident
        self.destroyed = False
        self.walker_control = None
        self.vehicle_control = None

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(
            x=self.xyz[0], y=self.xyz[1], z=self.xyz[2]))

    def get_velocity(self):
        return SimpleNamespace(x=5.0, y=0.0, z=0.0)

    def apply_control(self, control):
        self.walker_control = control

    def set_target_velocity(self, velocity):
        self.vehicle_control = velocity

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self, fail_vehicle=False):
        self.fail_vehicle = fail_vehicle
        self.spawns = []
        self.actors = []

    def get_blueprint_library(self):
        return self

    def filter(self, pattern):
        return [pattern]

    def try_spawn_actor(self, blueprint, transform):
        self.spawns.append((blueprint, transform))
        if self.fail_vehicle and blueprint.startswith("vehicle"):
            return None
        actor = FakeActor([transform.location.x, transform.location.y,
                           transform.location.z], len(self.spawns))
        self.actors.append(actor)
        return actor

    def get_actors(self):
        return SimpleNamespace(filter=lambda pattern: self.actors[1:])


def fake_carla():
    class C:
        @staticmethod
        def Location(*xyz):
            return SimpleNamespace(x=xyz[0], y=xyz[1], z=xyz[2])

        @staticmethod
        def Rotation(yaw):
            return SimpleNamespace(yaw=yaw)

        @staticmethod
        def Transform(location, rotation):
            return SimpleNamespace(location=location, rotation=rotation)

        @staticmethod
        def Vector3D(x, y, z):
            return SimpleNamespace(x=x, y=y, z=z)

        @staticmethod
        def WalkerControl(direction, speed, jump):
            return SimpleNamespace(direction=direction, speed=speed, jump=jump)
    return C


def scene(variant):
    return json.loads((ROOT/('scene-'+variant+'.json')).read_text())


def rows(variant):
    s = scene(variant)
    result = []
    for i in range(FRAMES):
        t = i*.05
        vx = -30+5*t
        walk_start = 7.2 if variant == "yield_before_vehicle" else 0
        py = min(8.0, -8+1.4*max(t-walk_start, 0))
        result.append({'case_id':s['case_id'], 'frame':1000+i,
                       'time_s':t, 'pedestrian_actor_id':11,
                       'vehicle_actor_id':22,
                       'pedestrian_xyz_m':[0,py,.2],
                       'vehicle_xyz_m':[vx,-1.75,.3],
                       'vehicle_velocity_xyz_mps':[5,0,0],
                       'all_native_vehicles':[{'actor_id':22,
                                               'xyz_m':[vx,-1.75,.3],
                                               'velocity_xyz_mps':[5,0,0]}]})
    return result


def write_attempt(root, variant, *, vehicle_shift=0):
    root.mkdir()
    shutil.copy(ROOT/'candidate-overpass.xodr', root/'map.xodr')
    shutil.copy(ROOT/('scene-'+variant+'.json'), root/'scene.json')
    source = rows(variant)
    if vehicle_shift:
        for row in source:
            row['vehicle_xyz_m'][1] += vehicle_shift
            row['all_native_vehicles'][0]['xyz_m'][1] += vehicle_shift
    (root/'body.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in source))
    (root/'frames.jsonl').write_text(''.join(json.dumps(
        {'frame':r['frame'],'time_s':r['time_s']})+'\n' for r in source))
    (root/'reviewed-site-source.txt').write_text('Synthetic overpass site review fixture\n')
    (root/'municipal-designation-source.txt').write_text('Synthetic designation review fixture\n')
    packet = {'format':'c188132-reviewed-overpass-site-v1',
              'provenance_kind':'synthetic_fixture',
              'case_id':scene(variant)['case_id'],
              'map_sha256':sha(root/'map.xodr'),
              'crossing_point_xy_m':[0.0,0.0],
              'surface_road_id':1,'deck_road_id':2,
              'roadway_y_bounds_m':[-3.5,3.5],
              'provided_overhead_crossing':True,
              'usable_deck_access':True,
              'independent_review':{'reviewer':'synthetic unit fixture',
                                    'source':'reviewed-site-source.txt',
                                    'sha256':sha(root/'reviewed-site-source.txt')},
              'municipal_designation':{'prohibited':variant=='designated_prohibition',
                                       'source':'municipal-designation-source.txt',
                                       'sha256':sha(root/'municipal-designation-source.txt')}}
    (root/'reviewed-site.json').write_text(json.dumps(packet))
    paths = {'map':'map.xodr','scene':'scene.json',
             'body_history':'body.jsonl','frame_map':'frames.jsonl',
             'site_review':'reviewed-site.json',
             'site_review_source':'reviewed-site-source.txt',
             'municipal_source':'municipal-designation-source.txt'}
    manifest = {'format':'c188132-original-sources-v1'}
    manifest.update({key:{'path':name,'sha256':sha(root/name)}
                     for key,name in paths.items()})
    (root/'original-sources.json').write_text(json.dumps(manifest))


class OverpassSourceTests(unittest.TestCase):
    def test_all_exact_scene_sources(self):
        source = validate_map(ROOT/'candidate-overpass.xodr')
        self.assertEqual(source['deck_z_m'], 5)
        for variant in CASES:
            self.assertEqual(validate_case(scene(variant), ROOT/'candidate-overpass.xodr'), source)
            self.assertEqual(set(camera_placements(scene(variant))), set(CAMERA_SPECS))

    def test_reject_fake_elevated_deck_and_stale_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'map.xodr'
            path.write_text((ROOT/'candidate-overpass.xodr').read_text().replace('a="5"', 'a="0"'))
            with self.assertRaisesRegex(ValueError, 'elevated'):
                validate_map(path)
        bad = scene(CASES[0]); bad['map_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_case(bad, ROOT/'candidate-overpass.xodr')

    def test_spawn_and_control_real_calls(self):
        world = FakeWorld(); carla = fake_carla(); s = scene(CASES[0])
        walker, vehicle = spawn_pair(world, carla, s)
        self.assertEqual(len(world.spawns), 2)
        self.assertEqual(world.spawns[0][1].rotation.yaw, 90)
        self.assertEqual(request_controls(carla, s, walker, vehicle)['walker_requested_mps'], 0)
        self.assertEqual(walker.walker_control.speed, 0)
        vehicle.xyz[0] = 7.0
        self.assertEqual(request_controls(carla, s, walker, vehicle)['walker_requested_mps'], 1.4)
        self.assertEqual(vehicle.vehicle_control.x, 5.0)
        snap = SimpleNamespace(frame=1000, timestamp=SimpleNamespace(elapsed_seconds=0.0))
        self.assertEqual(native_sample(s, snap, walker, vehicle)['vehicle_xyz_m'][0], 7.0)
        extra = FakeActor([12.0, -1.75, .3], 33)
        world.actors.append(extra)
        self.assertEqual([item['actor_id'] for item in native_sample(
            s, snap, walker, vehicle, world)['all_native_vehicles']], [2, 33])

    def test_failed_second_spawn_cleans_first(self):
        world = FakeWorld(fail_vehicle=True)
        with self.assertRaisesRegex(RuntimeError, 'vehicle spawn'):
            spawn_pair(world, fake_carla(), scene(CASES[0]))

    def test_original_order_differs_with_requested_hold(self):
        wait = measure_original(scene(CASES[0]), rows(CASES[0]))
        enter = measure_original(scene(CASES[1]), rows(CASES[1]))
        self.assertTrue(wait['pedestrian_entered_after_vehicle_passed'])
        self.assertFalse(enter['pedestrian_entered_after_vehicle_passed'])
        self.assertEqual(wait['legal_right_of_way'], 'unresolved')

    def test_original_source_rejections(self):
        s = scene(CASES[0]); source = rows(CASES[0])
        source[9]['frame'] += 1
        with self.assertRaisesRegex(ValueError, 'frame gap'):
            measure_original(s, source)
        source = rows(CASES[0]); source[9]['vehicle_xyz_m'] = None
        with self.assertRaisesRegex(ValueError, 'vehicle_xyz'):
            measure_original(s, source)
        with self.assertRaisesRegex(ValueError, '900-frame'):
            measure_original(s, rows(CASES[0])[:-1])

    def test_all_vehicle_inventory_and_selected_join(self):
        s = scene(CASES[0])
        source = rows(CASES[0])
        other = {'actor_id':33, 'xyz_m':[12.0, -1.75, .3],
                 'velocity_xyz_mps':[0.0, 0.0, 0.0]}
        for row in source:
            row['all_native_vehicles'].append(other)
        self.assertEqual(measure_original(s, source)[
            'observed_native_vehicle_actor_ids'], [22, 33])
        source[5]['all_native_vehicles'] = []
        with self.assertRaisesRegex(ValueError, 'all-vehicle inventory'):
            measure_original(s, source)
        source = rows(CASES[0])
        source[5]['all_native_vehicles'][0]['xyz_m'][0] += 1
        with self.assertRaisesRegex(ValueError, 'selected vehicle differs'):
            measure_original(s, source)

    def test_pair_rejects_extra_vehicle_source_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'first', Path(tmp)/'second'
            write_attempt(first, CASES[0])
            write_attempt(second, CASES[1])
            rows_path = second/'body.jsonl'
            source = [json.loads(line) for line in rows_path.read_text().splitlines()]
            source[5]['all_native_vehicles'].append({
                'actor_id':33, 'xyz_m':[12.0,-1.75,.3],
                'velocity_xyz_mps':[0.0,0.0,0.0]})
            rows_path.write_text(''.join(json.dumps(row)+'\n' for row in source))
            manifest_path = second/'original-sources.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['body_history']['sha256'] = sha(rows_path)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'all-vehicle inventory changed'):
                audit_pair(first, second, 'entry_timing', diagnostic=True)

    def test_sealed_source_manifest_and_missing_evidence(self):
        variant = CASES[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'attempt'
            write_attempt(root, variant)
            self.assertEqual(audit_saved(root, diagnostic=True)['measurement']['frames'], FRAMES)
            (root/'body.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError, 'stale original source'):
                audit_saved(root, diagnostic=True)

    def test_entry_and_exception_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp)/v for v in CASES]
            for root, variant in zip(roots, CASES):
                write_attempt(root, variant)
            self.assertEqual(audit_pair(roots[0], roots[1], 'entry_timing', diagnostic=True)[
                'comparison_id'], 'entry_timing')
            self.assertEqual(audit_pair(roots[1], roots[2], 'designated_exception', diagnostic=True)[
                'comparison_id'], 'designated_exception')
            with self.assertRaisesRegex(ValueError, 'wrong entry-timing pair'):
                audit_pair(roots[1], roots[2], 'entry_timing', diagnostic=True)

    def test_production_pair_reaudits_both_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'first', Path(tmp)/'second'
            write_attempt(first, CASES[0])
            write_attempt(second, CASES[1])
            for root in (first, second):
                shutil.copy(root/'map.xodr', root/'candidate-overpass.xodr')
            def reviewed(root, *, pixel_review, processing_receipt):
                self.assertEqual(pixel_review, root/'original-pixel-review.json')
                self.assertTrue(str(processing_receipt).endswith('.json'))
                return audit_saved(root, diagnostic=True)
            with patch('delivery_audit.audit', side_effect=reviewed) as original:
                answer = audit_pair(first, second, 'entry_timing',
                                    first_processing=first/'processing.json',
                                    second_processing=second/'processing.json')
                self.assertEqual(answer['comparison_id'], 'entry_timing')
                self.assertEqual(original.call_count, 2)
            with patch('delivery_audit.audit', side_effect=[
                    audit_saved(first, diagnostic=True),
                    ValueError('second original pixel visibility review incomplete')]) as original:
                with self.assertRaisesRegex(ValueError, 'second original pixel visibility'):
                    audit_pair(first, second, 'entry_timing',
                               first_processing=first/'processing.json',
                               second_processing=second/'processing.json')
                self.assertEqual(original.call_count, 2)
            with self.assertRaisesRegex(ValueError, 'both saved processing receipts required'):
                audit_pair(first, second, 'entry_timing')

    def test_comparison_rejects_changed_vehicle(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'first', Path(tmp)/'second'
            write_attempt(first, CASES[0])
            write_attempt(second, CASES[1], vehicle_shift=.1)
            with self.assertRaisesRegex(ValueError, 'vehicle trajectory changed'):
                audit_pair(first, second, 'entry_timing', diagnostic=True)

    def test_reviewed_site_is_required_and_source_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'attempt'
            write_attempt(root, CASES[2])
            packet = root/'reviewed-site.json'
            with self.assertRaisesRegex(ValueError, 'original reviewed site source required'):
                audit_saved(root)
            self.assertTrue(inspect_site(packet, root/'map.xodr', scene(CASES[2]),
                                         diagnostic=True)['designation_prohibited'])
            wrong = json.loads(packet.read_text())
            wrong['case_id'] = scene(CASES[0])['case_id']
            packet.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'another case'):
                inspect_site(packet, root/'map.xodr', scene(CASES[2]), diagnostic=True)
            wrong['case_id'] = scene(CASES[2])['case_id']
            wrong['municipal_designation']['prohibited'] = False
            packet.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'municipal designation differs'):
                inspect_site(packet, root/'map.xodr', scene(CASES[2]), diagnostic=True)
            wrong['municipal_designation']['prohibited'] = True
            packet.write_text(json.dumps(wrong))
            (root/'municipal-designation-source.txt').write_text('tampered source\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                inspect_site(packet, root/'map.xodr', scene(CASES[2]), diagnostic=True)


if __name__ == '__main__':
    unittest.main()
