import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_site", ROOT / "native_site.py")
SITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SITE)


class Map:
    name = "NativeIntersection"

    def to_opendrive(self):
        return "<OpenDRIVE>original map bytes</OpenDRIVE>"

    def get_waypoint(self, location, project_to_road=True):
        junction = abs(location.x) < 0.01 and abs(location.y) < 0.01
        return SimpleNamespace(
            transform=SimpleNamespace(location=location,
                                      rotation=SimpleNamespace(yaw=0.0)), road_id=1, lane_id=1,
            id=100 if junction else 101, is_junction=junction,
            get_junction=lambda: SimpleNamespace(id=7))


class World:
    def get_map(self):
        return Map()

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda value: SimpleNamespace(id=value) if value in {
            "vehicle.sedan", "vehicle.bicycle"} else None)


CARLA = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values))


def request(root):
    asset = root / "asset.source"
    asset.write_bytes(b"source-reviewed-Native-rider-asset")
    review = {"format": "c111260-reviewed-rider-asset-v1", "kind": "bicycle",
              "asset_source_path": str(asset),
              "asset_source_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
              "person_actor_id": 42,
              "blueprint_id": "vehicle.bicycle", "moped": False,
              "motorized": False, "wheel_diameters_in": [26, 26]}
    path = root / "review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    return {"rider_kind": "bicycle", "rider_asset_review_path": str(path),
            "rider_asset_review_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "motor_blueprint_id": "vehicle.sedan", "junction_id": 7,
            "ego_route_xy": [[-20, 0], [0, 0], [20, 0]],
            "rider_route_xy": [[0, -20], [0, 0], [0, 20]]}


class NativeSiteTests(unittest.TestCase):
    def test_original_map_routes_and_review_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = SITE.survey(World(), CARLA, request(base), base / "survey")
            packet = SITE.verify(base / "survey", refs["site"], expected_kind="bicycle")
            self.assertEqual(packet["junction_id"], 7)
            self.assertEqual(packet["physical_visibility"], "pending")
            self.assertEqual(SITE.verify_live(World(), CARLA, base / "survey", refs["site"],
                                              expected_kind="bicycle")["map_sha256"], packet["map_sha256"])
            (base / "survey" / "native-map.xodr").write_text("altered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash drift"):
                SITE.verify(base / "survey", refs["site"], expected_kind="bicycle")

    def test_changed_loaded_native_map_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = SITE.survey(World(), CARLA, request(base), base / "survey")
            class ChangedMap(Map):
                def to_opendrive(self):
                    return "<OpenDRIVE>different loaded map</OpenDRIVE>"
            class ChangedWorld(World):
                def get_map(self):
                    return ChangedMap()
            with self.assertRaisesRegex(ValueError, "loaded Native map differs"):
                SITE.verify_live(ChangedWorld(), CARLA, base / "survey", refs["site"],
                                 expected_kind="bicycle")

    def test_review_hash_and_route_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            req = request(base)
            req["rider_asset_review_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "reviewed rider asset source"):
                SITE.survey(World(), CARLA, req, base / "rejected")
            req = request(base)
            req["rider_route_xy"] = [[-20, 1], [0, 1], [20, 1]]
            with self.assertRaisesRegex(ValueError, "junction mismatch"):
                SITE.survey(World(), CARLA, req, base / "other")

    def test_changed_review_binding_rejected_after_site_reseal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = SITE.survey(World(), CARLA, request(base), base / "survey")
            packet_path = base / "survey" / refs["site"]["path"]
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["rider"]["wheel_diameters_in"] = [30, 30]
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            refs["site"]["sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "rider review binding"):
                SITE.verify(base / "survey", refs["site"], expected_kind="bicycle")


if __name__ == "__main__":
    unittest.main()
