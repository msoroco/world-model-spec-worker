"""CPU tests for source-gated electric device construction."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'electric_asset.py'
SPEC = importlib.util.spec_from_file_location('c230207_electric_asset', MODULE)
electric_asset = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(electric_asset)


class Blueprint:
    def __init__(self, blueprint_id):
        self.id = blueprint_id
        self.role_name = None

    def has_attribute(self, name):
        return name == 'role_name'

    def set_attribute(self, name, value):
        if not self.has_attribute(name):
            raise ValueError(name)
        self.role_name = value


class Library:
    def __init__(self, blueprint_id):
        self.blueprint_id = blueprint_id

    def filter(self, blueprint_id):
        return [Blueprint(self.blueprint_id)] if blueprint_id == self.blueprint_id else []

    def find(self, blueprint_id):
        return Blueprint(self.blueprint_id)


class Actor:
    def __init__(self, blueprint_id):
        self.id = 42
        self.type_id = blueprint_id
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, blueprint_id):
        self.library = Library(blueprint_id)
        self.actor_id = blueprint_id
        self.spawned = None

    def get_blueprint_library(self):
        return self.library

    def spawn_actor(self, blueprint, transform):
        self.spawned_blueprint = blueprint
        self.spawned = Actor(self.actor_id)
        return self.spawned


class ElectricAssetTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[4] / '.runtime-work' / 'c230207-electric-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'review.txt'
        source.write_text('Reviewed electric motor and geometry evidence.\n')
        self.review = {
            'machine_class': 'electric_bicycle',
            'blueprint_id': 'vehicle.reviewed.ebike',
            'source_kind': 'reviewed_native_asset',
            'reviewer': 'independent asset reviewer',
            'review_date': '2026-11-27',
            'classification_conclusion': 'electric_bicycle',
            'power_source_evidence': 'review.txt: motor and battery',
            'device_geometry_evidence': 'review.txt: cycle frame and pedals',
            'source_refs': [{'path': 'review.txt',
                             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
        }

    def test_exact_reviewed_asset_binds_without_claiming_pixels(self):
        world = World(self.review['blueprint_id'])
        actor, bound = electric_asset.spawn_asset(
            world, 'electric_bicycle', self.review, self.root, object(),
            role_name='c230207_reviewed_electric_subject')
        self.assertEqual(actor.id, 42)
        self.assertTrue(bound['classification_review_bound'])
        self.assertFalse(bound['original_class_pixels_verified'])
        self.assertEqual(world.spawned_blueprint.role_name,
                         'c230207_reviewed_electric_subject')

    def test_role_name_must_be_assignment_bound(self):
        with self.assertRaisesRegex(ValueError, 'role attribute'):
            electric_asset.spawn_asset(World(self.review['blueprint_id']),
                                       'electric_bicycle', self.review, self.root,
                                       object(), role_name='unrelated_actor')

    def test_ordinary_bicycle_and_changed_class_fail(self):
        wrong = dict(self.review, blueprint_id='vehicle.bh.crossbike')
        with self.assertRaisesRegex(ValueError, 'Ordinary bicycle'):
            electric_asset.bind_asset(Library(wrong['blueprint_id']),
                                      'electric_bicycle', wrong, self.root)
        with self.assertRaisesRegex(ValueError, 'Exact electric device class'):
            electric_asset.bind_asset(Library(self.review['blueprint_id']),
                                      'electric_scooter', self.review, self.root)

    def test_missing_or_changed_source_and_live_asset_fail(self):
        changed = dict(self.review, source_refs=[{'path': 'review.txt', 'sha256': '0' * 64}])
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            electric_asset.bind_asset(Library(self.review['blueprint_id']),
                                      'electric_bicycle', changed, self.root)
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            electric_asset.bind_asset(Library('vehicle.other'),
                                      'electric_bicycle', self.review, self.root)

    def test_unreviewed_or_unclassified_asset_fails_before_spawn(self):
        for missing in ('reviewer', 'review_date', 'power_source_evidence',
                        'device_geometry_evidence', 'source_refs'):
            with self.subTest(missing=missing):
                review = dict(self.review)
                review.pop(missing)
                world = World(review['blueprint_id'])
                with self.assertRaisesRegex(ValueError, 'review|evidence|references'):
                    electric_asset.spawn_asset(world, 'electric_bicycle', review,
                                               self.root, object())
                self.assertIsNone(world.spawned)

    def test_spawn_readback_rejects_wrong_actor(self):
        world = World(self.review['blueprint_id'])
        world.actor_id = 'vehicle.other'
        with self.assertRaisesRegex(ValueError, 'Spawned device differs'):
            electric_asset.spawn_asset(world, 'electric_bicycle', self.review,
                                       self.root, object())
        self.assertTrue(world.spawned.destroyed)


if __name__ == '__main__':
    unittest.main()
