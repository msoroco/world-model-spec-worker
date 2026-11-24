import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owned_runner", HERE / "owned_runner.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = HERE.name + "__steady_travel"


class OwnedRunnerTests(unittest.TestCase):
    def test_reviewed_site_bound_and_actor_destroyed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site.json"
            source = {"diagnostic_fixture": False, "site_source_sha256": "1" * 64}
            site.write_text(json.dumps(source) + "\n")
            actor = Mock()
            session = types.SimpleNamespace(world=object(), carla=object(),
                                             capture_adapter=object(), person_id="person-1")
            output = root / "attempt"
            with patch.object(MODULE, "spawn_ego", return_value=actor) as spawn, \
                    patch.object(MODULE, "capture", return_value={"case_id": CASE, "diagnostic_fixture": True}) as capture:
                receipt = MODULE.capture_reviewed(session, site, CASE, output)
            spawn.assert_called_once_with(session.world, session.carla, source, CASE)
            self.assertEqual(capture.call_args.args[3:6], (source, CASE, "person-1"))
            actor.destroy.assert_called_once()
            self.assertEqual((output / "site-source.json").read_bytes(), site.read_bytes())
            self.assertEqual(receipt["site_packet_sha256"], __import__("hashlib").sha256(site.read_bytes()).hexdigest())
            self.assertTrue(receipt["diagnostic_fixture"])

    def test_capture_failure_still_destroys_actor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site.json"
            site.write_text('{"diagnostic_fixture": false}\n')
            actor = Mock()
            session = types.SimpleNamespace(world=object(), carla=object(),
                                             capture_adapter=object(), person_id="person-1")
            with patch.object(MODULE, "spawn_ego", return_value=actor), \
                    patch.object(MODULE, "capture", side_effect=ValueError("camera failure")):
                with self.assertRaisesRegex(ValueError, "camera failure"):
                    MODULE.capture_reviewed(session, site, CASE, root / "attempt")
            actor.destroy.assert_called_once()

    def test_unsourced_or_existing_attempt_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site.json"
            site.write_text('{"diagnostic_fixture": true}\n')
            with self.assertRaisesRegex(ValueError, "Reviewed original site"):
                MODULE.capture_reviewed(object(), site, CASE, root / "attempt")
            site.write_text('{"diagnostic_fixture": false}\n')
            (root / "attempt").mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                MODULE.capture_reviewed(object(), site, CASE, root / "attempt")


if __name__ == "__main__":
    unittest.main()
