"""Bundle the exact unselected 30-second primary emergency-source construction."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "native"

TEST = '''import json
from pathlib import Path
import tempfile
import unittest
from runner import check
from prove import make_source
from measure import measure

class SourceContract(unittest.TestCase):
    def test_exact_plan(self):
        row = check()
        self.assertEqual(row["frames"], 600)
        self.assertFalse(row["siren_output_observed"])

    def test_source_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            files = make_source(Path(temp), "probe_a")
            result = measure(*files)
            self.assertEqual(result["siren_observed_frames"], 200)
            self.assertEqual(result["siren_outside_documented_response_frames"], 0)
            self.assertIsNone(result["physical_legal_verdict"])
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    case_id = HERE.name + "__probe_a"
    files = [{"path": name, "content": (NATIVE / name).read_text()}
             for name in ("config.json", "runner.py", "measure.py", "prove.py")]
    files.append({"path": "tests/test_source.py", "content": TEST})
    construction = {
        "case_id": case_id, "cell_id": "C109028", "law_id": "NRS-484D-400-5",
        "actor": "emergency_vehicle_driver", "entrypoint": "runner.py",
        "status": "unselected_cpu_diagnostic", "files": files,
        "recording_description": "Thirty-second emergency approach source contract; siren acoustics, authorization and original Native state unverified."}
    path = HERE / "draft-candidates" / "probe_a" / "primary" / "construction.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(construction, indent=2) + "\n")
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name, "status": "draft_not_selected",
                "cases": [{"case_id": case_id, "kind": "draft_not_selected",
                           "construction": str(path.relative_to(HERE)),
                           "construction_sha256": sha(path), "candidates": []}],
                "original_native_observed": False, "delivery_ready": False}
    (HERE / "draft-execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()["cases"])}))
