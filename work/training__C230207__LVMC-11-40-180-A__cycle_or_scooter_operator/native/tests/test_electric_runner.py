"""CPU acquisition gates for an electric asset, without CARLA connection."""
import unittest

from electric_runner import behavior_plan, check, electric_config, electric_context


class Actor:
    def __init__(self, actor_id, type_id):
        self.id = actor_id
        self.type_id = type_id


class ElectricRunnerTests(unittest.TestCase):
    def test_class_specific_config_and_capture_plan(self):
        for kind in ('electric_bicycle', 'electric_scooter'):
            config = {'machine_class': kind,
                      'electric_asset_review': {'machine_class': kind},
                      'electric_asset_source_root': '/external/reviewed-assets'}
            self.assertEqual(electric_config(config)[0], kind)
        self.assertEqual(check()['frames'], 600)
        self.assertEqual(len(check()['cameras']), 4)
        self.assertEqual(behavior_plan('mounted_sidewalk')['target_speed_mps'],
                         behavior_plan('walk_cycle')['target_speed_mps'])

    def test_unbound_or_relative_source_rejected(self):
        base = {'machine_class': 'electric_scooter',
                'electric_asset_review': {'machine_class': 'electric_scooter'},
                'electric_asset_source_root': '/external/reviewed-assets'}
        with self.assertRaisesRegex(ValueError, 'Absolute original'):
            electric_config({**base, 'electric_asset_source_root': 'reviewed-assets'})
        with self.assertRaisesRegex(ValueError, 'Exact electric asset review'):
            electric_config({**base, 'electric_asset_review': {'machine_class': 'electric_bicycle'}})
        with self.assertRaisesRegex(ValueError, 'Exact electric machine'):
            electric_config({**base, 'machine_class': 'human_propelled_bicycle'})

    def test_recorded_context_joins_original_actor_and_review_sources(self):
        actor = Actor(17, 'vehicle.reviewed.escooter')
        bound = {'machine_class': 'electric_scooter',
                 'blueprint_id': actor.type_id, 'native_actor_id': actor.id,
                 'review_source_sha256': {'review.txt': 'a' * 64},
                 'review_sha256': 'b' * 64}
        readback = {'sign': {'id': '100'}, 'sidewalk': [{'lane_id': -2}]}
        plan = behavior_plan('walk_cycle')
        context = electric_context('electric_scooter', bound, actor, readback,
                                   'walk_cycle', Actor(18, 'walker.pedestrian.0001'), plan)
        self.assertEqual(context['rider_class'], 'electric_scooter')
        self.assertEqual(context['electric_asset_binding']['native_actor_id'], 17)
        self.assertEqual(context['operator_actor_id'], 18)
        self.assertFalse(context['geographic_identity_verified'])
        self.assertFalse(context['physical_sign_pixels_verified'])
        with self.assertRaisesRegex(ValueError, 'does not join'):
            electric_context('electric_scooter', {**bound, 'native_actor_id': 19},
                             actor, readback, 'walk_cycle', None, plan)
        with self.assertRaisesRegex(ValueError, 'does not join'):
            electric_context('electric_scooter', {**bound, 'review_source_sha256': {}},
                             actor, readback, 'walk_cycle', None, plan)
