"""Small fake Native publication checks; no CARLA connection or physical claim."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(REPO / ".runtime-work/c10301-publication-tests"))
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from PIL import Image
from worker_exchange import native_output
from worker_exchange import media

SPEC = importlib.util.spec_from_file_location("alley_runtime_publication", ROOT / "runtime_publication.py")
PUBLICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLICATION)
CASE = ROOT.name + "__steady_travel"


def _jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


class RuntimePublicationTests(unittest.TestCase):
    def _attempt(self, root):
        root.mkdir()
        (root / "capture/native").mkdir(parents=True)
        (root / "camera-png").mkdir()
        (root / "runner.py").write_text("# original runner\n")
        (root / "construction.json").write_text(json.dumps({"recording_description": {
            "channels": [], "context_inputs": []}}) + "\n")
        (root / "config.json").write_text(json.dumps({"law_id": "LVMC-11-22-010",
            "cell_id": "C10301", "actor": "motor_vehicle_driver", "duration_s": 45,
            "rate_hz": 20, "requested_speed_mps": 2}) + "\n")
        (root / "capture.json").write_text(json.dumps({"case_id": CASE,
            "duration_frames": 2, "diagnostic_fixture": True}) + "\n")
        (root / "capture/manifest.json").write_text(json.dumps({"case_id": CASE,
            "frames": 2, "extraction_confirmed": True}) + "\n")
        rows = [{"frame": i + 10, "time_s": i / 20, "position_m": [i, 0, 0]}
                for i in range(2)]
        _jsonl(root / "trace.jsonl", rows)
        _jsonl(root / "ego.jsonl", [{"native_frame": i + 10,
                                      "native_time_s": i / 20} for i in range(2)])
        _jsonl(root / "context.jsonl", [{"native_frame": i + 10,
                                          "native_time_s": i / 20} for i in range(2)])
        _jsonl(root / "operation.jsonl", [{"frame": i, "time_s": i / 20}
                                             for i in range(2)])
        _jsonl(root / "capture/evidence.jsonl", [{"original_frame": i + 10} for i in range(2)])
        graph_rows = []
        for i in range(2):
            graph = root / "capture/native/graphs/base" / f"{i + 10:08d}.adapter.json"
            graph.parent.mkdir(parents=True, exist_ok=True)
            graph.write_text(json.dumps({"format": "native-adapter-graph-v1",
                                         "metadata": {"frame": i + 10},
                                         "nodes": [], "edges": []}) + "\n")
            graph_rows.append({"frame": i + 10,
                               "adapter_graph": f"graphs/base/{i + 10:08d}.adapter.json"})
        _jsonl(root / "capture/native/frames.jsonl", graph_rows)
        image = Image.new("RGB", (4, 4), "blue")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        source = buffer.getvalue()
        import hashlib
        checks = []
        for i in range(2):
            cameras = {}
            for name in PUBLICATION.VIEWS:
                (root / "camera-png" / f"{i:04d}-{name}.png").write_bytes(source)
                cameras[name] = {"sha256": hashlib.sha256(source).hexdigest()}
            checks.append({"native_frame": i + 10, "native_time_s": i / 20,
                           "cameras": cameras})
        _jsonl(root / "camera-frame-map.jsonl", checks)

    def test_positive_publication_and_restoration_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt"
            self._attempt(root)
            def fake_encoder(command, check):
                self.assertTrue(check)
                Path(command[-1]).write_bytes(b"fake video fixture")
            with patch.object(PUBLICATION, "VIEWS", {name: (video, 4, 4)
                    for name, (video, _, _) in PUBLICATION.VIEWS.items()}), \
                    patch.object(media, "audit", return_value={"frames": 2}):
                receipt = PUBLICATION.publish_original(root, CASE, expected_frames=2,
                                                       encoder=fake_encoder)
            self.assertEqual(receipt["frames"], 2)
            self.assertEqual(json.loads((root / "result.json").read_text())["provenance_kind"], "native")
            self.assertEqual(len((root / "video_frames.jsonl").read_text().splitlines()), 2)
            self.assertEqual(json.loads((root / "acquisition-provenance.json").read_text())["provenance_kind"], "native")
            with self.assertRaisesRegex(ValueError, "restoration receipt"):
                PUBLICATION.seal_reviewed(root, {"restored": True})
            sealed = PUBLICATION.seal_reviewed(root, {"restored": True,
                                                      "source": "fake adapter world-settings readback"})
            self.assertEqual(sealed["frames"], 2)
            self.assertTrue((root / "capture-seal.json").is_file())

    def test_missing_graph_or_changed_camera_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt"
            self._attempt(root)
            (root / "capture/native/frames.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original capture source"):
                PUBLICATION.publish_original(root, CASE, expected_frames=2)
            _jsonl(root / "capture/native/frames.jsonl", [{"frame": i + 11,
                "adapter_graph": f"graphs/base/{i + 10:08d}.adapter.json"} for i in range(2)])
            with self.assertRaisesRegex(ValueError, "Original frame identities differ"):
                PUBLICATION.publish_original(root, CASE, expected_frames=2)
            _jsonl(root / "capture/native/frames.jsonl", [{"frame": i + 10,
                "adapter_graph": f"graphs/base/{i + 10:08d}.adapter.json"} for i in range(2)])
            (root / "capture/native/graphs/base/00000010.adapter.json").unlink()
            with self.assertRaisesRegex(ValueError, "adapter graph source missing"):
                PUBLICATION.publish_original(root, CASE, expected_frames=2)
            graph = root / "capture/native/graphs/base/00000010.adapter.json"
            graph.write_text(json.dumps({"format": "native-adapter-graph-v1",
                                         "metadata": {"frame": 10},
                                         "nodes": [], "edges": []}) + "\n")
            (root / "camera-png/0000-overview.png").write_bytes(b"corrupt")
            with patch.object(PUBLICATION, "VIEWS", {name: (video, 4, 4)
                    for name, (video, _, _) in PUBLICATION.VIEWS.items()}):
                with self.assertRaises(Exception):
                    PUBLICATION.publish_original(root, CASE, expected_frames=2)
