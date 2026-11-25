"""Source-shaped Core publication joins; fixtures make no acceptance claim."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_publication import verify_core_join


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ROOT.name + "__blocked_intervening"
        (self.root / "capture/native/graphs/abstract").mkdir(parents=True)
        (self.root / "road.xodr").write_text("<OpenDRIVE/>\n")
        (self.root / "source-packet.json").write_text(json.dumps({
            "case_id": self.case, "source_kind": "original_saved_acquisition",
            "fixture_scope": "synthetic source-shaped join test only"}) + "\n")
        streams = {name: [] for name in ("trace.jsonl", "capture/evidence.jsonl",
                                         "capture/native/frames.jsonl",
                                         "video_frames.jsonl", "pedestrian_history.jsonl")}
        for i in range(3):
            frame, when = i + 10, i * .05
            graph_ref = f"graphs/abstract/{frame:08d}.adapter.json"
            (self.root / "capture/native" / graph_ref).write_text(json.dumps({
                "format": "native-adapter-graph-v1", "metadata": {"frame": frame},
                "nodes": [], "edges": []}) + "\n")
            streams["trace.jsonl"].append({"frame": frame, "time_s": when})
            streams["capture/evidence.jsonl"].append({"original_frame": frame,
                                                        "recording_time_s": when})
            streams["capture/native/frames.jsonl"].append({"frame": frame,
                                                               "adapter_graph": graph_ref})
            streams["video_frames.jsonl"].append({"carla_frame": frame,
                                                    "video_frame": i, "time_s": when})
            streams["pedestrian_history.jsonl"].append({"frame": frame, "time_s": when})
        for name, rows in streams.items():
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        sha = lambda name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        (self.root / "capture/manifest.json").write_text(json.dumps({
            "case_id": self.case, "acquisition": "original_live_run", "frames": 3,
            "extraction_confirmed": True,
            "sources": {name: sha(name) for name in ("trace.jsonl", "road.xodr")}}) + "\n")

    def test_source_shaped_positive_and_changed_graph_negative(self):
        proof = verify_core_join(self.root, self.case, expected_frames=3)
        self.assertEqual(proof["frame_count"], 3)
        graph = self.root / "capture/native/graphs/abstract/00000011.adapter.json"
        payload = json.loads(graph.read_text())
        payload["metadata"]["frame"] = 12
        graph.write_text(json.dumps(payload) + "\n")
        with self.assertRaisesRegex(ValueError, "graph structure"):
            verify_core_join(self.root, self.case, expected_frames=3)

    def test_trace_change_and_frame_gap_rejected(self):
        trace = self.root / "trace.jsonl"
        trace.write_text(trace.read_text().replace('"frame": 11', '"frame": 99'))
        with self.assertRaisesRegex(ValueError, "same-frame"):
            verify_core_join(self.root, self.case, expected_frames=3)


if __name__ == "__main__":
    unittest.main()
