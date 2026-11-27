"""Accepted-source admission tests use disposable bytes under .runtime-work."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accepted_source import ASSIGNMENT, CASES, SourceError, verify
from review_accepted import review


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AcceptedSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c158190-accepted-source-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rid = next(iter(CASES))
        self.case = CASES[self.rid]
        self.trace = self.root / "trace.json"
        self.video = self.root / "raw.mkv"
        self.video.write_bytes(b"fixture original video bytes")
        self.observations = {
            "scenes": [{"t": i * 50, "subject": 1, "users": []}
                       for i in range(900)],
        }
        self.source = self.root / "inputs" / ASSIGNMENT
        self.metadata = self.source / "accepted" / self.rid / "metadata.json"
        self.metadata.parent.mkdir(parents=True)
        self.assignment_path = self.source / "assignment.json"
        self.assignment_path.write_text(json.dumps({
            "assignment_id": ASSIGNMENT,
            "cell": {"cell_id": "C158190", "control": "stop_sign"},
        }) + "\n")
        self.evidence_path = self.source / "evidence.json"
        original_root = "/fixture/recordings/" + self.rid + "/evidence/"
        self.row = {
            "recording_id": self.rid, "case_id": self.case,
            "cell_id": "C158190", "actor": "motor_vehicle_driver",
            "law_id": "NRS-484B-257-1", "status": "accepted", "frames": 900,
            "acceptance": {
                "trace_source": original_root + "traffic_spec/trace.json",
                "video_source": original_root + "raw.mkv",
                "case_id": self.case, "cell_id": "C158190",
                "actor": "motor_vehicle_driver", "law_id": "NRS-484B-257-1",
                "split": "testing", "frames": 900,
            },
        }
        self.save()

    def save(self):
        self.trace.write_text(json.dumps(self.observations) + "\n")
        self.row["trace_sha256"] = digest(self.trace.read_bytes())
        self.row["video_sha256"] = digest(self.video.read_bytes()) if self.video.exists() else "0" * 64
        self.row["acceptance"]["trace_sha256"] = self.row["trace_sha256"]
        self.row["acceptance"]["video_sha256"] = self.row["video_sha256"]
        self.metadata.write_text(json.dumps(self.row) + "\n")
        self.evidence_path.write_text(json.dumps({"recordings": [{
            "recording_id": self.rid, "sets": ["demo-test", "full-test"],
            "membership": {key: self.row[key] for key in
                           ("recording_id", "case_id", "cell_id", "actor", "law_id", "status")},
            "sources": [{"path": str(self.metadata.relative_to(self.root)),
                         "sha256": digest(self.metadata.read_bytes())}],
        }]}) + "\n")

    def test_both_exact_frozen_record_ids_admit_only_matching_original_bytes(self):
        for rid, case in CASES.items():
            with self.subTest(rid=rid):
                self.rid, self.case = rid, case
                self.metadata = self.source / "accepted" / rid / "metadata.json"
                self.metadata.parent.mkdir(parents=True, exist_ok=True)
                self.row["recording_id"] = rid
                self.row["case_id"] = case
                self.row["acceptance"]["case_id"] = case
                root = "/fixture/recordings/" + rid + "/evidence/"
                self.row["acceptance"]["trace_source"] = root + "traffic_spec/trace.json"
                self.row["acceptance"]["video_source"] = root + "raw.mkv"
                self.save()
                self.assertEqual(verify(self.root, rid, self.trace, self.video)["case_id"], case)
                result = review(self.root, rid, self.trace, self.video)
                self.assertEqual(result["original_observations"]["scene_count"], 900)
                self.assertEqual(result["original_observations"]["last_timestamp_ms"], 44950)
                self.assertIn("legal coverage", result["finding"])

    def test_missing_or_tampered_original_bytes_rejected(self):
        self.trace.write_text("{}\n")
        with self.assertRaisesRegex(SourceError, "trace hash"):
            verify(self.root, self.rid, self.trace, self.video)
        self.save()
        self.video.write_bytes(b"different")
        with self.assertRaisesRegex(SourceError, "video hash"):
            verify(self.root, self.rid, self.trace, self.video)
        self.save()
        self.video.unlink()
        with self.assertRaisesRegex(SourceError, "missing"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_unknown_or_rewritten_frozen_identity_rejected(self):
        with self.assertRaisesRegex(SourceError, "two frozen accepted IDs"):
            verify(self.root, "invented", self.trace, self.video)
        self.row["case_id"] = ASSIGNMENT + "__invented"
        self.save()
        with self.assertRaisesRegex(SourceError, "identity"):
            verify(self.root, self.rid, self.trace, self.video)
        self.row["case_id"] = self.case
        self.metadata.write_text(self.metadata.read_text() + "\n")
        with self.assertRaisesRegex(SourceError, "evidence inventory"):
            verify(self.root, self.rid, self.trace, self.video)

    def test_non_core_packet_rejected_even_when_source_hash_matches(self):
        self.observations = {"site": {"governing_control": "stop_sign"},
                             "frames": [{"frame": i} for i in range(900)]}
        self.save()
        with self.assertRaisesRegex(SourceError, "Core trace scenes"):
            review(self.root, self.rid, self.trace, self.video)

    def test_missing_or_nonmonotonic_core_scenes_rejected(self):
        self.observations["scenes"].pop()
        self.save()
        with self.assertRaisesRegex(SourceError, "complete original Core scene"):
            review(self.root, self.rid, self.trace, self.video)
        self.observations["scenes"].append({"t": 44950, "subject": 1, "users": []})
        self.observations["scenes"][200]["t"] = 9950
        self.save()
        with self.assertRaisesRegex(SourceError, "timestamps must increase"):
            review(self.root, self.rid, self.trace, self.video)

    def test_missing_core_scene_timestamp_rejected(self):
        self.observations["scenes"][200].pop("t")
        self.save()
        with self.assertRaisesRegex(SourceError, "scene timestamp"):
            review(self.root, self.rid, self.trace, self.video)


if __name__ == "__main__":
    unittest.main()
