import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_right_response import audit


class RightResponseAuditTests(unittest.TestCase):
    def test_rejects_changed_overtaker_even_with_rebound_source_hash(self):
        folder = Path(__file__).resolve().parents[1]
        reference = folder / "diagnostic.json"
        no_yield = folder / "diagnostic-no-yield.json"
        self.assertGreater(audit(reference, no_yield)["precompletion_right_shift_difference_m"], .2)
        with tempfile.TemporaryDirectory() as directory:
            changed = json.loads(no_yield.read_text())
            rows = [json.loads(line) for line in changed["files"]["overtake_bodies_original.jsonl"].splitlines()]
            rows[2]["overtaker"]["body_corners_xy_m"][0][0] += 1.
            content = "".join(json.dumps(row) + "\n" for row in rows)
            changed["files"]["overtake_bodies_original.jsonl"] = content
            receipt = json.loads(changed["files"]["overtake_source_receipt.json"])
            receipt["source_sha256"]["overtake_bodies_original.jsonl"] = hashlib.sha256(content.encode()).hexdigest()
            changed["files"]["overtake_source_receipt.json"] = json.dumps(receipt)
            target = Path(directory) / "changed.json"
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "fixed actor"):
                audit(reference, target)


if __name__ == "__main__":
    unittest.main()
