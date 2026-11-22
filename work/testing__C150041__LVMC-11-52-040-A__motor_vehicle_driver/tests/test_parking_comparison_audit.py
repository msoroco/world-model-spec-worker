"""Four measured comparisons reject request-only or source-only changes."""
import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_comparison_audit import PAIRS, audit
from parking_finalizer import finalize
from parking_pose import construct
from source_review import validate
from test_parking_finalizer import write_history
from test_source_review import fixture


class ComparisonAuditTests(unittest.TestCase):
    def test_all_four_pairs_use_measured_original_geometry(self):
        with TemporaryDirectory() as tmp:
            packet_path, packet = fixture(tmp)
            for activity in ("park", "stand"):
                packet["context"]["activity"] = activity
                packet_path.write_text(json.dumps(packet))
                context = validate(packet_path, source_root=tmp)
                results = {}
                for suffix in (activity + "_parallel_lawful",
                               activity + "_angled_lawful",
                               activity + "_parallel_reverse"):
                    pose = construct(context, suffix)
                    history, digest = write_history(tmp, pose, [1, 0, 0])
                    results[suffix] = finalize(packet_path, tmp, suffix, history, digest)
                for comparison_id, (first, second, _) in PAIRS.items():
                    if comparison_id.startswith(activity + "_"):
                        proof = audit(results[first], results[second], comparison_id)
                        self.assertGreater(proof["measured_separation_deg"], 10)
                        self.assertFalse(proof["physical_acceptance_claimed"])
                        self.assertEqual(proof["legal_judgment"], "unresolved")

    def test_request_only_and_changed_source_rejected(self):
        with TemporaryDirectory() as tmp:
            packet_path, _ = fixture(tmp)
            context = validate(packet_path, source_root=tmp)
            pose = construct(context, "park_parallel_lawful")
            history, digest = write_history(tmp, pose, [0, 0])
            left = finalize(packet_path, tmp, "park_parallel_lawful", history, digest)
            right = copy.deepcopy(left)
            right["case_id"] = right["case_id"].replace("parallel_lawful", "angled_lawful")
            right["original_history_sha256"] = "different-control-only-history"
            with self.assertRaisesRegex(ValueError, "measured orientation difference"):
                audit(left, right, "park_parallelism")
            right["source_packet_sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "source packet differs"):
                audit(left, right, "park_parallelism")


if __name__ == "__main__":
    unittest.main()
