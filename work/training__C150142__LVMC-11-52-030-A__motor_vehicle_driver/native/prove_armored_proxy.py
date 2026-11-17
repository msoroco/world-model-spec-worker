"""Exercise the requested Native attachment calls and failure cleanup."""
import unittest
import armored_proxy


class Actor:
    def __init__(self, ident):
        self.id = ident
        self.type_id = armored_proxy.PANEL_BLUEPRINT
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Library:
    def __init__(self):
        self.requests = []

    def find(self, name):
        self.requests.append(name)
        return name


class World:
    def __init__(self, fail_at=None):
        self.calls = []
        self.actors = []
        self.fail_at = fail_at

    def try_spawn_actor(self, blueprint, transform, attach_to=None):
        self.calls.append((blueprint, transform, attach_to))
        if len(self.calls) == self.fail_at:
            return None
        actor = Actor(len(self.calls))
        self.actors.append(actor)
        return actor


class Carla:
    @staticmethod
    def Location(*values):
        return values

    @staticmethod
    def Rotation(*values):
        return values

    @staticmethod
    def Transform(location, rotation):
        return location, rotation


class ProxyProof(unittest.TestCase):
    def setUp(self):
        self.config = {'native_blueprint': armored_proxy.BASE_BLUEPRINT,
                       'service_class': 'armored_car',
                       'armor_proxy_kind': 'attached_box_panels_v1',
                       'armor_panel_blueprint': armored_proxy.PANEL_BLUEPRINT}

    def test_four_physical_attachment_requests(self):
        world, library, ego = World(), Library(), object()
        actors, readback = armored_proxy.spawn(world, library, Carla, ego, self.config)
        self.assertEqual(len(actors), 4)
        self.assertEqual(library.requests, [armored_proxy.PANEL_BLUEPRINT])
        self.assertEqual([r['name'] for r in readback],
                         ['left_side', 'right_side', 'rear', 'roof'])
        self.assertTrue(all(call[2] is ego for call in world.calls))
        self.assertEqual([call[1][0] for call in world.calls],
                         [p[1] for p in armored_proxy.PANELS])
        self.assertLess(world.calls[0][1][0][1], 0)
        self.assertGreater(world.calls[1][1][0][1], 0)

    def test_failed_panel_cleans_up_prior_attachments(self):
        world = World(fail_at=3)
        with self.assertRaisesRegex(RuntimeError, 'rear'):
            armored_proxy.spawn(world, Library(), Carla, object(), self.config)
        self.assertEqual(len(world.actors), 2)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_wrong_base_and_class(self):
        for key, value in [('native_blueprint', 'vehicle.carlamotors.firetruck'),
                           ('service_class', 'emergency_vehicle'),
                           ('armor_panel_blueprint', 'static.prop.unknown')]:
            config = {**self.config, key: value}
            with self.assertRaises(ValueError):
                armored_proxy.validate(config)

    def test_retained_readback_requires_all_distinct_panels(self):
        world = World()
        _, panels = armored_proxy.spawn(world, Library(), Carla, object(), self.config)
        readback = {'source_kind': 'synthetic_native_sample',
                    'base_actor_id': 20,
                    'base_blueprint': armored_proxy.BASE_BLUEPRINT,
                    'panels': panels,
                    'legal_armored_identity_verified': False}
        observed = armored_proxy.verify_readback(readback, [{'actor_id': 20}], self.config)
        self.assertEqual(observed['panels_observed'], 4)
        self.assertFalse(observed['legal_armored_identity_verified'])
        for mutation in (
                {**readback, 'panels': panels[:-1]},
                {**readback, 'base_actor_id': 21},
                {**readback, 'legal_armored_identity_verified': True},
                {**readback, 'panels': [panels[0], panels[0], *panels[2:]]}):
            with self.assertRaises(ValueError):
                armored_proxy.verify_readback(mutation, [{'actor_id': 20}], self.config)


if __name__ == '__main__':
    unittest.main()
