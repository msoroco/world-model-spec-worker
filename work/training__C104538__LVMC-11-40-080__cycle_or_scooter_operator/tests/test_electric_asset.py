import sys
import hashlib
import tempfile
import json
from types import SimpleNamespace
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
from electric_asset import (validate_blueprint, bind_reviewed_asset,
                            spawn_reviewed_electric, LEGAL_CLASS_SOURCES)


class Blueprint:
    def __init__(self, blueprint_id):
        self.id = blueprint_id


class Library:
    def __init__(self, ids):
        self.ids = ids

    def filter(self, pattern):
        return [Blueprint(item) for item in self.ids if item == pattern]

    def find(self, blueprint_id):
        return Blueprint(blueprint_id)


class ElectricAssetTest(unittest.TestCase):
    def test_exact_review_source_binding_for_each_electric_class(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            source = root / 'asset-review.json'
            source.write_text(json.dumps({'scope': 'unit-test-only'}) + '\n')
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            for machine_class in LEGAL_CLASS_SOURCES:
                with self.subTest(machine_class=machine_class):
                    blueprint_id = 'vehicle.unit_test.' + machine_class
                    evidence = {'machine_class': machine_class,
                                'blueprint_id': blueprint_id,
                                'source_kind': 'reviewed_native_asset',
                                'reviewer': 'unit-test-reviewer',
                                'class_review': {'reviewer': 'unit-test-reviewer',
                                                 'legal_sources': list(LEGAL_CLASS_SOURCES[machine_class]),
                                                 'conclusion': machine_class},
                                'source_refs': [{'path': source.name, 'sha256': checksum}]}
                    selected = bind_reviewed_asset(Library([blueprint_id]),
                                                   machine_class, evidence, root)
                    self.assertEqual(selected['review_source_sha256'], {source.name: checksum})
                    self.assertTrue(selected['original_pixel_review_pending'])
                    class World:
                        def get_blueprint_library(self):
                            return Library([blueprint_id])

                        def spawn_actor(self, blueprint, transform):
                            self.transform = transform
                            return SimpleNamespace(id=17, type_id=blueprint.id)
                    world = World()
                    actor, captured = spawn_reviewed_electric(
                        world, machine_class, evidence, root, object())
                    self.assertEqual(actor.id, captured['native_actor_id'])
                    self.assertFalse(captured['original_class_pixels_verified'])
                    destroyed = []
                    class WrongWorld(World):
                        def spawn_actor(self, blueprint, transform):
                            return SimpleNamespace(id=18, type_id='vehicle.other',
                                                   destroy=lambda: destroyed.append(True))
                    with self.assertRaisesRegex(ValueError, 'Spawned electric actor differs'):
                        spawn_reviewed_electric(WrongWorld(), machine_class,
                                                evidence, root, object())
                    self.assertEqual(destroyed, [True])
                    evidence['source_refs'][0]['sha256'] = '0' * 64
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        bind_reviewed_asset(Library([blueprint_id]), machine_class,
                                            evidence, root)
                    evidence['source_refs'][0]['sha256'] = checksum
                    evidence['source_refs'][0]['path'] = '../asset-review.json'
                    with self.assertRaisesRegex(ValueError, 'inside source root'):
                        bind_reviewed_asset(Library([blueprint_id]), machine_class,
                                            evidence, root)
    def test_rejects_bicycle_alias_for_both_electric_classes(self):
        for machine_class in ("electric_bicycle", "electric_scooter"):
            with self.subTest(machine_class=machine_class):
                evidence = {"machine_class": machine_class,
                            "blueprint_id": "vehicle.bh.crossbike",
                            "source_kind": "reviewed_native_asset", "reviewer": "asset-review"}
                with self.assertRaisesRegex(ValueError, "Ordinary bicycle"):
                    validate_blueprint(Library(["vehicle.bh.crossbike"]),
                                       machine_class, "vehicle.bh.crossbike", evidence)

    def test_requires_exact_live_asset_and_review(self):
        evidence = {"machine_class": "electric_bicycle",
                    "blueprint_id": "vehicle.example.electric_bicycle",
                    "source_kind": "reviewed_native_asset", "reviewer": "asset-review"}
        with self.assertRaisesRegex(ValueError, "unavailable"):
            validate_blueprint(Library([]), "electric_bicycle",
                               evidence["blueprint_id"], evidence)
        self.assertTrue(validate_blueprint(Library([evidence["blueprint_id"]]),
                                           "electric_bicycle", evidence["blueprint_id"],
                                           evidence)["native_asset_found"])
        evidence["source_kind"] = "synthetic_label"
        with self.assertRaisesRegex(ValueError, "Reviewed"):
            validate_blueprint(Library([evidence["blueprint_id"]]),
                               "electric_bicycle", evidence["blueprint_id"], evidence)
