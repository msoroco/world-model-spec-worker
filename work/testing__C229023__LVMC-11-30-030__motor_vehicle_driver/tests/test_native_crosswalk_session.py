import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_crosswalk_session as module
from crosswalk_measurements import ASSIGNMENT_ID


class FakeActors:
    instances = []

    def __init__(self, **kwargs):
        self.controls = 0
        self.closed = False
        self.actor_ids = {"ego": "1", "lead": "2", "pedestrian": "3"}
        self.instances.append(self)

    def control(self):
        self.controls += 1

    def observe(self, frame):
        return {role: {"actor_id": identity, "source_ref": f"frame/{frame}"}
                for role, identity in self.actor_ids.items()}

    def close(self):
        self.closed = True


class FakeCameras:
    instances = []

    def __init__(self, **kwargs):
        self.frames = 0
        self.closed = False
        self.instances.append(self)

    def append(self, frame):
        self.frames += 1
        return {name: type("Image", (), {"frame": frame})()
                for name in ("overview", "approach", "reference_corner", "driver_reference")}

    def close(self, *, require_complete=True):
        self.closed = True
        if require_complete and self.frames != 900:
            raise RuntimeError("incomplete camera frames")


class FakeRecorder:
    instances = []

    def __init__(self, **kwargs):
        self.rows = 0
        self.instances.append(self)

    def append(self, **kwargs):
        self.rows += 1

    def write(self, output):
        if self.rows != 900:
            raise RuntimeError("incomplete recorder rows")
        return {"frame_count": self.rows}


class FakeWorld:
    def __init__(self):
        self.frame = 99

    def tick(self):
        self.frame += 1
        return self.frame


class SessionTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        site = {"junction_kind": "road_intersection", "alley_junction": False,
                "road_axis": {"origin": [0, 0], "forward": [1, 0]},
                "opposite_sidewalk_lateral_lines": [[[10, -4], [10, 4]], [[12, -4], [12, 4]]]}
        self.site = self.root / "site.json"
        self.site.write_text(json.dumps(site))
        self.proposal = {"case_id": ASSIGNMENT_ID + "__unmarked_pass",
                         "source": {"path": str(self.site), "sha256": hashlib.sha256(self.site.read_bytes()).hexdigest()},
                         "map_id": "TownReviewed", "crosswalk_kind": "unmarked",
                         "crosswalk_polygon": [[10, -4], [10, 4], [12, 4], [12, -4]],
                         "lead_stop_purpose": "permit_pedestrian",
                         "source_inventory": {name: {"sha256": "a" * 64, "citation": name}
                                              for name in ("map", "curb_or_edge", "stopped_purpose")}}
        self.output = self.root / "output"
        self.output.mkdir()
        FakeActors.instances.clear()
        FakeCameras.instances.clear()
        FakeRecorder.instances.clear()

    def _patches(self):
        return (patch.object(module, "run_sourced_world", side_effect=lambda **kwargs: kwargs["capture"](kwargs["world"])),
                patch.object(module, "NativeCrosswalkActors", FakeActors),
                patch.object(module, "NativeCrosswalkCameras", FakeCameras),
                patch.object(module, "NativeCrosswalkRecorder", FakeRecorder))

    def test_full_acquisition_and_cleanup(self):
        first, second, third, fourth = self._patches()
        with first, second, third, fourth:
            result = module.capture_case(world=FakeWorld(), carla=object(), proposal=self.proposal, output=self.output)
        self.assertEqual(result["receipt"]["frame_count"], 900)
        self.assertEqual(FakeActors.instances[0].controls, 900)
        self.assertEqual(FakeCameras.instances[0].frames, 900)
        self.assertTrue(FakeActors.instances[0].closed)
        self.assertTrue(FakeCameras.instances[0].closed)
        self.assertEqual(len(result["video_paths"]), 4)

    def test_context_rejects_wrong_intersection_and_nonempty_output(self):
        site = json.loads(self.site.read_text())
        site["junction_kind"] = "alley"
        with self.assertRaisesRegex(ValueError, "road intersection"):
            module._context(self.proposal, site, {"ego": "1", "lead": "2", "pedestrian": "3"})
        (self.output / "existing").write_text("original")
        with self.assertRaisesRegex(ValueError, "fresh empty"):
            module.capture_case(world=FakeWorld(), carla=object(), proposal=self.proposal, output=self.output)


if __name__ == "__main__":
    unittest.main()
