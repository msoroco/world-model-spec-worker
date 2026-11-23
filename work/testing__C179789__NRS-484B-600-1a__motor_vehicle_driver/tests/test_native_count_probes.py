import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_count_probes import construct, validate_packet


class _Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _Map:
    def to_opendrive(self):
        return "source-road"


class _Blueprints:
    def __init__(self, missing=False):
        self.missing = missing

    def find(self, name):
        return None if self.missing else name


class _World:
    def __init__(self, missing=False, fail_second=False):
        self.blueprints = _Blueprints(missing)
        self.fail_second = fail_second
        self.actors = []

    def get_map(self):
        return _Map()

    def get_blueprint_library(self):
        return self.blueprints

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.actors:
            return None
        actor = _Actor()
        self.actors.append(actor)
        return actor


class NativeCountProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "probe.json"
        self.packet = {
            "format": "c179789-native-count-probe-v1", "case_id": "case__animal_above",
            "kind": "additional_animal_count", "expected_count": 2,
            "reviewer": "CPU fixture", "source_citation": "synthetic CPU fixture only",
            "map_sha256": hashlib.sha256(b"source-road").hexdigest(),
            "actors": [{"id": f"animal-{i}", "role": "animal",
                        "blueprint_id": "source-bound-animal", "source_citation": "synthetic CPU fixture only",
                        "transform": {"x": float(i), "y": 1.0, "z": 0.0, "yaw": 0.0}}
                       for i in range(2)]}
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.packet))

    def test_source_gated_spawn_and_identity(self):
        world = _World()
        result = construct(world, self.path, case_id="case__animal_above",
                           kind="additional_animal_count", expected_count=2,
                           transform_factory=lambda **kw: kw)
        self.assertEqual(len(result["actors"]), 2)
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(result["packet_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_missing_blueprint_and_partial_spawn_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "blueprint unavailable"):
            construct(_World(missing=True), self.path, case_id="case__animal_above",
                      kind="additional_animal_count", expected_count=2,
                      transform_factory=lambda **kw: kw)
        world = _World(fail_second=True)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            construct(world, self.path, case_id="case__animal_above",
                      kind="additional_animal_count", expected_count=2,
                      transform_factory=lambda **kw: kw)
        self.assertTrue(world.actors[0].destroyed)

    def test_rejects_confounded_or_unsourced_actor_inventory(self):
        self.packet["actors"][1]["role"] = "pedestrian"
        self.write()
        with self.assertRaisesRegex(ValueError, "source or placement"):
            validate_packet(self.path, case_id="case__animal_above",
                            kind="additional_animal_count", expected_count=2)
        self.packet["actors"][1]["role"] = "animal"
        self.packet["actors"][1]["id"] = "animal-0"
        self.write()
        with self.assertRaisesRegex(ValueError, "duplicated"):
            validate_packet(self.path, case_id="case__animal_above",
                            kind="additional_animal_count", expected_count=2)

    def test_rejects_changed_map_source(self):
        self.packet["map_sha256"] = "0" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE source differs"):
            construct(_World(), self.path, case_id="case__animal_above",
                      kind="additional_animal_count", expected_count=2,
                      transform_factory=lambda **kw: kw)


if __name__ == "__main__":
    unittest.main()
