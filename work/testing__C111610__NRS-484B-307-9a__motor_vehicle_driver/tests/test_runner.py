import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
import test_saved_turn


class FakeWorld:
    def __init__(self):
        self.frame = 40

    def tick(self):
        self.frame += 1
        return self.frame


class FakeState:
    def __init__(self, *, bad=False):
        self.commands = []
        self.closed = False
        self.bad = bad

    def command(self, index):
        self.commands.append(index)

    def read(self, frame, index):
        camera_frame = frame + int(self.bad)
        return {"native_frame": frame, "telemetry": {"frame": index},
                "cameras": {name: {"frame": camera_frame}
                            for name in runner.CAMERAS}}

    def close(self):
        self.closed = True


class FakeModule:
    def __init__(self, state):
        self.state = state

    def bind(self, world, site, command, actors):
        return self.state


class RunnerTests(unittest.TestCase):
    def setUp(self):
        fixture = test_saved_turn.SavedTurnTests()
        fixture.setUp()
        self.addCleanup(fixture.tmp.cleanup)
        self.root = fixture.root

    def test_reviewed_adapter_hash_and_escape(self):
        path = self.root / "reviewed.py"
        path.write_text("def bind(world, site, command):\n    return object()\n")
        site = {"adapter_source": {"path": path.name,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.assertTrue(callable(runner.load_reviewed_adapter(site, self.root).bind))
        site["adapter_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            runner.load_reviewed_adapter(site, self.root)
        site["adapter_source"]["path"] = "../foreign.py"
        with self.assertRaisesRegex(ValueError, "path invalid"):
            runner.load_reviewed_adapter(site, self.root)

    def test_command_then_same_tick_source(self):
        site_raw = json.dumps({"source_kind": "original_native_site_review"}).encode()
        source = {"path": "reviewed.py", "sha256": "a" * 64}
        state = FakeState()
        adapter = runner.OriginalAdapter(FakeWorld(), {}, site_raw,
                                         FakeModule(state), source, {}, {})
        self.assertEqual(adapter.tick()["native_frame"], 41)
        self.assertEqual(state.commands, [0])
        self.assertEqual(adapter.source_attestation()["site_sha256"],
                         hashlib.sha256(site_raw).hexdigest())
        adapter.close()
        self.assertTrue(state.closed)
        bad = runner.OriginalAdapter(FakeWorld(), {}, site_raw,
                                     FakeModule(FakeState(bad=True)), source, {}, {})
        with self.assertRaisesRegex(ValueError, "same-tick source mismatch"):
            bad.tick()


if __name__ == "__main__":
    unittest.main()
