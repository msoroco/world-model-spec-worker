"""CPU checks of the independent original-source review joins."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from original_review import CAMERAS, REQUIRED_FEATURES, audit_original_review
from delivery_audit import audit_delivery


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class OriginalReviewTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory(dir=REPO / ".runtime-work")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.case = ROOT.name + "__blocked_intervening"
        self.sample_frames = (0, 450, 800)
        frame_map = self.root / "video_frames.jsonl"
        frame_map.write_text("".join(json.dumps({"carla_frame": 500 + frame,
            "video_frame": frame, "time_s": frame / 20}) + "\n" for frame in range(900)))
        write(self.root / "source-packet.json", {"case_id": self.case})
        self.packet_sha = sha(self.root / "source-packet.json")
        write(self.root / "lifecycle-receipt.json", {
            "case_id": self.case, "source_packet_sha256": self.packet_sha,
            "world_restore": {"restored": True}})
        write(self.root / "acquisition-context.json", {
            "source_packet_sha256": self.packet_sha})
        write(self.root / "traffic-plan.json", {"actor_ids": [42]})
        with self._create_evidence() as stream:
            for frame in range(900):
                stream.write(json.dumps({"original_frame": 500 + frame, "actor_id": 7,
                    "original_observations": {"participants": [{"actor_id": 7},
                                                                {"actor_id": 42}]}}) + "\n")
        write(self.root / "result.json", {"case_id": self.case,
            "provenance_kind": "native", "diagnostic_fixture": False,
            "maneuver_completed": True, "physical_checks": {"maneuver": {"status": "met"}}})
        write(self.root / "capture-seal.json", {
            "format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": False, "restoration": {"restored": True},
            "sources": {"acquisition-context.json": sha(self.root / "acquisition-context.json"),
                        "result.json": sha(self.root / "result.json")}})
        sealed = {}
        decoded = {}
        reviewed = {}
        for name in CAMERAS:
            video = self.root / (name + ".mkv")
            video.write_bytes(name.encode())
            sealed[name] = {"path": video.name, "sha256": sha(video)}
            decoded[name] = {"width": 1280, "height": 720, "frame_count": 900,
                             "profile_dimensions": True}
            reviewed[name] = {"video_sha256": sha(video), "samples": [
                {"frame_index": frame, "rgb_sha256": "a" * 64,
                 "visible_features": sorted(REQUIRED_FEATURES[name].get(phase, set()))}
                for phase, frame in zip(("entry", "bypass", "return"), self.sample_frames)]}
        self.saved_audit = {"case_id": self.case,
            "source_kind": "original_saved_acquisition",
            "source_packet_sha256": self.packet_sha,
            "measured_observables": {"highway_frames": [950],
                                     "first_sidewalk_return_frame": 1300},
            "sealed_camera_media": sealed, "decoded_camera_media": decoded}
        self.review = self.root / "independent-review.json"
        write(self.review, {"format": "worker-pedestrian-original-pixel-review",
            "case_id": self.case, "source_packet_sha256": self.packet_sha,
            "reviewer": "independent CPU fixture reviewer", "method": "frame RGB hash review",
            "walker_actor_id": 7, "cameras": reviewed})

    def _create_evidence(self):
        path = self.root / "capture/evidence.jsonl"
        path.parent.mkdir(parents=True)
        return path.open("w")

    def audit(self):
        with patch("original_review._decoded_frame_hashes",
                   return_value={frame: "a" * 64 for frame in self.sample_frames}):
            return audit_original_review(self.root, self.case,
                                         self.saved_audit, self.review)

    def test_reviewed_original_bytes_and_participant_census(self):
        receipt = self.audit()
        self.assertTrue(all(receipt["checks"].values()))
        self.assertEqual(receipt["participant_census"]["frames"], 900)
        self.assertEqual(receipt["legal_judgment"], "unresolved")

    def test_diagnostic_source_rejected(self):
        self.saved_audit["source_kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(ValueError, "original saved acquisition"):
            self.audit()

    def test_missing_participant_rejected(self):
        path = self.root / "capture/evidence.jsonl"
        rows = path.read_text().splitlines()
        row = json.loads(rows[400]); row["original_observations"]["participants"].pop()
        rows[400] = json.dumps(row)
        path.write_text("\n".join(rows) + "\n")
        with self.assertRaisesRegex(ValueError, "omits a required actor"):
            self.audit()

    def test_stale_camera_review_rejected(self):
        data = json.loads(self.review.read_text())
        data["cameras"]["approach"]["video_sha256"] = "0" * 64
        write(self.review, data)
        with self.assertRaisesRegex(ValueError, "stale camera bytes"):
            self.audit()

    def test_unreviewed_obstruction_rejected(self):
        data = json.loads(self.review.read_text())
        data["cameras"]["overview"]["samples"][1]["visible_features"].remove("obstruction")
        write(self.review, data)
        with self.assertRaisesRegex(ValueError, "visible original pixels"):
            self.audit()

    def test_incomplete_physical_result_rejected(self):
        data = json.loads((self.root / "result.json").read_text())
        data["maneuver_completed"] = False
        write(self.root / "result.json", data)
        seal = json.loads((self.root / "capture-seal.json").read_text())
        seal["sources"]["result.json"] = sha(self.root / "result.json")
        write(self.root / "capture-seal.json", seal)
        with self.assertRaisesRegex(ValueError, "physical maneuver is not complete"):
            self.audit()

    def test_delivery_requires_reviewed_original_source(self):
        with patch("delivery_audit.audit_saved", return_value=self.saved_audit), \
                patch("original_review._decoded_frame_hashes",
                      return_value={frame: "a" * 64 for frame in self.sample_frames}):
            receipt = audit_delivery(self.root, self.case, self.review)
        self.assertTrue(all(receipt["checks"].values()))
        self.assertEqual(receipt["physical_acceptance"],
                         "source_reviewed_pending_canonical_acceptance")


if __name__ == "__main__":
    unittest.main()
