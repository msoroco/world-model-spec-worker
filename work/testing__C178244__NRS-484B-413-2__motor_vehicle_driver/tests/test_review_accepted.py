"""Review bridge tests keep fixture bytes outside work/."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accepted_source import ASSIGNMENT
from review_accepted import review
from review_accepted_comparison import compare
from signal_distance import EvidenceError
from test_signal_distance import packet, write_sources


class ReviewAcceptedTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c178244-review-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rid = "fixture-recording"
        self.case_id = ASSIGNMENT + "__business_continuous"
        self.trace = self.root / "trace.json"
        self.video = self.root / "raw.mkv"
        self.trace.write_bytes(b'{"original_fixture":true}\n')
        self.video.write_bytes(b"fixture-video-bytes")
        meta = self.root / "inputs" / ASSIGNMENT / "accepted" / self.rid / "metadata.json"
        meta.parent.mkdir(parents=True)
        trace_hash = hashlib.sha256(self.trace.read_bytes()).hexdigest()
        video_hash = hashlib.sha256(self.video.read_bytes()).hexdigest()
        meta.write_text(json.dumps({
            "recording_id": self.rid, "case_id": self.case_id,
            "cell_id": "C178244", "actor": "motor_vehicle_driver",
            "law_id": "NRS-484B-413-2", "status": "accepted", "frames": 900,
            "trace_sha256": trace_hash, "video_sha256": video_hash,
            "acceptance": {"case_id": self.case_id, "frames": 900,
                           "trace_sha256": trace_hash, "video_sha256": video_hash},
        }) + "\n")
        self.packet = packet(case_id=self.case_id)
        evidence_path = self.root / "inputs" / ASSIGNMENT / "evidence.json"
        evidence_path.write_text(json.dumps({"recordings": [{
            "recording_id": self.rid,
            "membership": {"recording_id": self.rid, "case_id": self.case_id,
                           "cell_id": "C178244", "actor": "motor_vehicle_driver",
                           "law_id": "NRS-484B-413-2", "status": "accepted"},
            "sources": [{"path": str(meta.relative_to(self.root)),
                         "sha256": hashlib.sha256(meta.read_bytes()).hexdigest()}],
        }]}) + "\n")
        write_sources(self.root, self.packet)
        self.packet_path = self.root / "packet.json"
        self.save()
        self.bind_packet(self.rid, self.packet_path)

    def save(self):
        self.packet_path.write_text(json.dumps(self.packet) + "\n")

    def bind_packet(self, recording_id, packet_path):
        evidence_path = self.root / "inputs" / ASSIGNMENT / "evidence.json"
        evidence = json.loads(evidence_path.read_text())
        row, = [r for r in evidence["recordings"] if r["recording_id"] == recording_id]
        rel = str(packet_path.relative_to(self.root))
        row["sources"] = [s for s in row["sources"] if s["path"] != rel]
        row["sources"].append({"path": rel,
                               "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest()})
        evidence_path.write_text(json.dumps(evidence) + "\n")

    def test_source_bound_left_turn_measurement(self):
        finding = review(self.root, self.rid, self.trace, self.video,
                         self.packet_path, self.root)
        self.assertEqual(finding["case_id"], self.case_id)
        self.assertEqual(finding["measurement"]["turn_direction"], "left")
        self.assertEqual(len(finding["signal_sources_verified"]), 5)
        self.assertEqual(finding["packet_source_sha256"],
                         hashlib.sha256(self.packet_path.read_bytes()).hexdigest())

    def test_unbound_substitute_packet_rejected(self):
        self.packet["route_sha256"] = "substitute-route"
        self.save()
        with self.assertRaisesRegex(ValueError, "not bound to frozen accepted evidence"):
            review(self.root, self.rid, self.trace, self.video,
                   self.packet_path, self.root)

    def test_missing_frozen_packet_entry_rejected(self):
        evidence_path = self.root / "inputs" / ASSIGNMENT / "evidence.json"
        evidence = json.loads(evidence_path.read_text())
        evidence["recordings"][0]["sources"] = evidence["recordings"][0]["sources"][:1]
        evidence_path.write_text(json.dumps(evidence) + "\n")
        with self.assertRaisesRegex(ValueError, "not bound to frozen accepted evidence"):
            review(self.root, self.rid, self.trace, self.video,
                   self.packet_path, self.root)

    def test_right_turn_packet_rejected_for_frozen_cell(self):
        self.packet["turn_direction"] = "right"
        self.save()
        self.bind_packet(self.rid, self.packet_path)
        with self.assertRaisesRegex(EvidenceError, "left-turn"):
            review(self.root, self.rid, self.trace, self.video,
                   self.packet_path, self.root)

    def test_wrong_district_case_rejected(self):
        self.packet["district_class"] = "other"
        self.save()
        self.bind_packet(self.rid, self.packet_path)
        with self.assertRaisesRegex(EvidenceError, "district"):
            review(self.root, self.rid, self.trace, self.video,
                   self.packet_path, self.root)

    def second_side(self):
        folder = self.root / "second"
        folder.mkdir()
        trace = folder / "trace.json"
        video = folder / "raw.mkv"
        trace.write_bytes(b'{"original_fixture":"second"}\n')
        video.write_bytes(b"second-fixture-video-bytes")
        case_id = ASSIGNMENT + "__business_short"
        rid = "second-fixture-recording"
        meta = self.root / "inputs" / ASSIGNMENT / "accepted" / rid / "metadata.json"
        meta.parent.mkdir(parents=True)
        th = hashlib.sha256(trace.read_bytes()).hexdigest()
        vh = hashlib.sha256(video.read_bytes()).hexdigest()
        meta.write_text(json.dumps({
            "recording_id": rid, "case_id": case_id,
            "cell_id": "C178244", "actor": "motor_vehicle_driver",
            "law_id": "NRS-484B-413-2", "status": "accepted", "frames": 900,
            "trace_sha256": th, "video_sha256": vh,
            "acceptance": {"case_id": case_id, "frames": 900,
                           "trace_sha256": th, "video_sha256": vh},
        }) + "\n")
        evidence_path = self.root / "inputs" / ASSIGNMENT / "evidence.json"
        evidence = json.loads(evidence_path.read_text())
        evidence["recordings"].append({
            "recording_id": rid,
            "membership": {"recording_id": rid, "case_id": case_id,
                           "cell_id": "C178244", "actor": "motor_vehicle_driver",
                           "law_id": "NRS-484B-413-2", "status": "accepted"},
            "sources": [{"path": str(meta.relative_to(self.root)),
                         "sha256": hashlib.sha256(meta.read_bytes()).hexdigest()}],
        })
        evidence_path.write_text(json.dumps(evidence) + "\n")
        second = packet(start=10, case_id=case_id)
        write_sources(folder, second)
        packet_path = folder / "packet.json"
        packet_path.write_text(json.dumps(second) + "\n")
        self.bind_packet(rid, packet_path)
        return {"recording_id": rid, "trace": trace, "video": video,
                "packet": packet_path, "source_root": folder}, second

    def first_side(self):
        return {"recording_id": self.rid, "trace": self.trace,
                "video": self.video, "packet": self.packet_path,
                "source_root": self.root}

    def test_accepted_business_pair_reports_physical_difference(self):
        second, _ = self.second_side()
        result = compare(self.root, "business", self.first_side(), second)
        self.assertEqual(len(result["accepted_recording_ids"]), 2)
        self.assertEqual(result["physical_comparison"]["case_ids"][0], self.case_id)

    def test_accepted_pair_rejects_changed_route(self):
        second, packet2 = self.second_side()
        packet2["route_sha256"] = "changed-route"
        second["packet"].write_text(json.dumps(packet2) + "\n")
        self.bind_packet(second["recording_id"], second["packet"])
        with self.assertRaisesRegex(EvidenceError, "route_sha256"):
            compare(self.root, "business", self.first_side(), second)

    def test_accepted_pair_rejects_duplicate_case(self):
        second, _ = self.second_side()
        with self.assertRaisesRegex(EvidenceError, "district pair"):
            compare(self.root, "residential", self.first_side(), second)


if __name__ == "__main__":
    unittest.main()
