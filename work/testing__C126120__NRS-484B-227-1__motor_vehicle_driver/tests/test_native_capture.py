"""CPU checks for source identity and original camera-frame acquisition."""
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import CameraBank, reviewed_context


class CaptureTests(unittest.TestCase):
    def test_reviewed_packet_binds_live_map_and_authority_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            authority = root / "authority.json"
            authority.write_text('{"public_authority_established": "unresolved"}')
            context = {"map_source_sha256": hashlib.sha256(b"road").hexdigest(),
                       "authority_review_source_sha256": hashlib.sha256(authority.read_bytes()).hexdigest(),
                       "opening_id": "opening-1"}
            source = root / "review.json"
            source.write_text(json.dumps({"context": context,"divider_props":[]}))
            scene = {"context": context,"divider_props":[],"reviewed_context_source": str(source),
                     "reviewed_context_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "authority_review_source": str(authority)}
            output = root / "attempt"
            output.mkdir()
            world = Mock()
            world.get_map.return_value.to_opendrive.return_value = "road"
            self.assertEqual(reviewed_context(scene, output, world)["context"], context)
            self.assertEqual((output/"reviewed-median-context.json").read_bytes(), source.read_bytes())
            scene["context"] = {**context, "opening_id": "other"}
            with self.assertRaisesRegex(ValueError, "geometry differs"):
                reviewed_context(scene, root, world)
            scene["context"] = context
            world.get_map.return_value.to_opendrive.return_value = "other road"
            with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
                reviewed_context(scene, root, world)
            world.get_map.return_value.to_opendrive.return_value = "road"
            authority.write_text("changed")
            with self.assertRaisesRegex(ValueError, "authority review source hash"):
                reviewed_context(scene, root, world)

    def test_camera_bank_spawns_four_sources_and_rejects_frame_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scene = {"context": {"opening_bounds_xy_m": [0,0,10,8]},
                     "route_xy_m": [[-8,2],[-2,2],[2,2],[8,2],[8,8]]}
            sensors = []
            world = Mock()
            world.get_blueprint_library.return_value.find.return_value = Mock()
            def spawn(*args, **kwargs):
                sensor = Mock()
                sensors.append((sensor, kwargs))
                return sensor
            world.spawn_actor.side_effect = spawn
            carla = types.SimpleNamespace(Location=lambda **k:k, Rotation=lambda **k:k,
                Transform=lambda location,rotation:(location,rotation))
            processes = []
            def encoder(*args, **kwargs):
                process = Mock()
                process.stdin = Mock(closed=False)
                process.wait.return_value = 0
                processes.append(process)
                return process
            ego = Mock()
            with patch("native_capture.subprocess.Popen", side_effect=encoder):
                bank = CameraBank(world, ego, root, carla, scene)
                self.assertEqual(len(sensors), 4)
                self.assertIs(sensors[-1][1]["attach_to"], ego)
                self.assertTrue(all(entry[1]["attach_to"] is None for entry in sensors[:-1]))
                for sensor,_ in sensors: sensor.listen.call_args.args[0](types.SimpleNamespace(frame=9,raw_data=b"pixels"))
                bank.append(9)
                self.assertTrue(all(p.stdin.write.call_args.args[0] == b"pixels" for p in processes))
                for sensor,_ in sensors: sensor.listen.call_args.args[0](types.SimpleNamespace(frame=11,raw_data=b"pixels"))
                with self.assertRaisesRegex(RuntimeError, "camera frame differs"):
                    bank.append(10)
                bank.close()
                self.assertTrue(all(sensor.stop.called and sensor.destroy.called for sensor,_ in sensors))


if __name__ == "__main__":
    unittest.main()
