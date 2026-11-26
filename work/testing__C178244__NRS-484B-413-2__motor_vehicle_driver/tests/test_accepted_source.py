"""Source admission tests use disposable bytes, never accepted recordings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accepted_source import ASSIGNMENT, SourceError, verify


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AcceptedSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c178244-accepted-source-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rid = "fixture-recording"
        self.trace = self.root / "trace.json"
        self.video = self.root / "raw.mkv"
        self.trace.write_bytes(b'{"fixture":true}\n')
        self.video.write_bytes(b"fixture-video-bytes")
        self.metadata = self.root / "inputs" / ASSIGNMENT / "accepted" / self.rid / "metadata.json"
        self.metadata.parent.mkdir(parents=True)
        self.evidence_path = self.root / "inputs" / ASSIGNMENT / "evidence.json"
        self.case = ASSIGNMENT + "__business_continuous"
        self.row = {
            "recording_id": self.rid, "case_id": self.case, "cell_id": "C178244",
            "actor": "motor_vehicle_driver", "law_id": "NRS-484B-413-2",
            "status": "accepted", "frames": 900,
            "trace_sha256": digest(self.trace.read_bytes()),
            "video_sha256": digest(self.video.read_bytes()),
        }
        self.row["acceptance"] = {
            "case_id": self.case, "frames": 900,
            "trace_sha256": self.row["trace_sha256"],
            "video_sha256": self.row["video_sha256"],
        }
        self.save()

    def save(self):
        self.metadata.write_text(json.dumps(self.row) + "\n")
        self.evidence_path.write_text(json.dumps({"recordings": [{
            "recording_id": self.rid,
            "membership": {key: self.row[key] for key in
                           ("recording_id", "case_id", "cell_id", "actor", "law_id", "status")},
            "sources": [{"path": str(self.metadata.relative_to(self.root)),
                         "sha256": digest(self.metadata.read_bytes())}],
        }]}) + "\n")

    def test_exact_hashes_admit_only_bytes(self):
        receipt = verify(self.root, self.rid, self.trace, self.video)
        self.assertEqual(receipt["case_id"], self.case)
        self.assertIn("still require independent audit", receipt["finding"])

    def test_trace_byte_change_rejected(self):
        self.trace.write_bytes(b'{"fixture":false}\n')
        with self.assertRaisesRegex(SourceError, "trace hash"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_video_byte_change_rejected(self):
        self.video.write_bytes(b"different-video-bytes")
        with self.assertRaisesRegex(SourceError, "video hash"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_other_case_or_actor_rejected(self):
        self.row["case_id"] = ASSIGNMENT + "__invented"
        self.save()
        with self.assertRaisesRegex(SourceError, "identity"):
            verify(self.root, self.rid, self.trace, self.video)
        self.row["case_id"] = self.case
        self.row["actor"] = "bus_driver"
        self.save()
        with self.assertRaisesRegex(SourceError, "identity"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_absent_original_rejected(self):
        self.video.unlink()
        with self.assertRaisesRegex(SourceError, "missing"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_rewritten_metadata_without_frozen_evidence_rejected(self):
        self.metadata.write_text(self.metadata.read_text() + "\n")
        with self.assertRaisesRegex(SourceError, "evidence inventory"):
            verify(self.root, self.rid, self.trace, self.video)


if __name__ == "__main__":
    unittest.main()
