import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("build_full_release_diagnostic", HERE / "build_full_release_diagnostic.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FullReleaseDiagnosticTest(unittest.TestCase):
    def test_complete_original_sources_and_distinct_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            summaries = MODULE.expand(temporary)
            self.assertEqual([s["frames"] for s in summaries], [320] * 3)
            self.assertTrue(all(s["bytes"] <= 2 * 1024 * 1024 for s in summaries))
            self.assertEqual([s["graph_packets"] for s in summaries], [640] * 3)
            entries = []
            for rank in range(3):
                path = Path(temporary) / f"yield_release_delay-{rank:04d}-candidate.json"
                source = json.loads(path.read_text())
                files = source["files"]
                participants = [json.loads(line) for line in files["intersection_participants.jsonl"].splitlines()]
                evidence = [json.loads(line) for line in files["capture/evidence.jsonl"].splitlines()]
                native = [json.loads(line) for line in files["capture/native/frames.jsonl"].splitlines()]
                trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
                self.assertEqual(len(participants), len(evidence))
                self.assertEqual(len(evidence), len(native))
                self.assertEqual(len(native), len(trace))
                self.assertTrue(all(v["frames"] == 320 for v in source["videos"]))
                self.assertEqual(len(source["videos"]), 4)
                self.assertEqual([row["frame"] for row in participants],
                                 [row["original_frame"] for row in evidence])
                self.assertEqual([row["frame"] for row in native],
                                 [row["frame"] for row in trace])
                graph_paths = {graph["path"] for graph in source["graphs"]}
                self.assertTrue(all("capture/native/" + row["base"] in graph_paths
                                    for row in native))
                source_rank = (0, 2, 1)[rank]
                entries.append(json.loads((Path(temporary) / "originals" /
                    f"yield_release_delay-{source_rank:04d}" / "config.json").read_text())
                               ["release_delay_frames"])
            self.assertEqual(entries, [0, 160, 80])


if __name__ == "__main__":
    unittest.main()
