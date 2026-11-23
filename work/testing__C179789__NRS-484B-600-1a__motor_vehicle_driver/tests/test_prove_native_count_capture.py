import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_count_capture import CountCapture
from prove_native_count_capture import prove


def snapshot(frame):
    return SimpleNamespace(frame=frame, timestamp=SimpleNamespace(elapsed_seconds=frame / 20))


class CountProofTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "original-count.jsonl"
        self.actor = object()
        self.packet = hashlib.sha256(b"packet").hexdigest()
        self.map_hash = hashlib.sha256(b"map").hexdigest()
        self.construction = {"case_id": "case__pedestrian_above", "kind": "additional_pedestrian_count",
                             "expected_count": 1, "actors": [self.actor],
                             "declared_blueprint_ids": ["walker.source"],
                             "packet_sha256": self.packet, "opendrive_sha256": self.map_hash}
        capture = CountCapture(self.construction)
        for frame in range(900):
            capture.append(snapshot(frame), lambda actor: {"actor_id": 51,
                           "type_id": "walker.source", "alive": frame < 450})
        capture.close(self.source)

    def check(self):
        return prove(self.source, case_id=self.construction["case_id"],
                     kind=self.construction["kind"], packet_sha256=self.packet,
                     opendrive_sha256=self.map_hash,
                     declared_blueprint_ids=["walker.source"])

    def test_uses_first_original_count_and_full_history(self):
        receipt = self.check()
        self.assertEqual((receipt["first_observed_count"], receipt["minimum_observed_count"],
                          receipt["maximum_observed_count"]), (1, 0, 1))
        self.assertFalse(receipt["physical_acceptance_claimed"])

    def test_rejects_wrong_packet_and_blueprint(self):
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            prove(self.source, case_id=self.construction["case_id"], kind=self.construction["kind"],
                  packet_sha256=hashlib.sha256(b"wrong").hexdigest(),
                  opendrive_sha256=self.map_hash, declared_blueprint_ids=["walker.source"])
        with self.assertRaisesRegex(ValueError, "readback mismatch"):
            prove(self.source, case_id=self.construction["case_id"], kind=self.construction["kind"],
                  packet_sha256=self.packet, opendrive_sha256=self.map_hash,
                  declared_blueprint_ids=["walker.other"])

    def test_rejects_seal_and_count_tamper(self):
        seal = self.source.with_name(self.source.name + ".seal.json")
        row = json.loads(self.source.read_text().splitlines()[0])
        row["observed_count"] = 2
        lines = self.source.read_text().splitlines()
        lines[0] = json.dumps(row, sort_keys=True)
        self.source.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            self.check()
        receipt = json.loads(seal.read_text())
        receipt["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        seal.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "not measured"):
            self.check()

    def test_rejects_resealed_slow_tick(self):
        seal = self.source.with_name(self.source.name + ".seal.json")
        lines = self.source.read_text().splitlines()
        row = json.loads(lines[1])
        row["native_elapsed_s"] = .1
        lines[1] = json.dumps(row, sort_keys=True)
        self.source.write_text("\n".join(lines) + "\n")
        receipt = json.loads(seal.read_text())
        receipt["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        seal.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "sample rate differs"):
            self.check()


if __name__ == "__main__":
    unittest.main()
