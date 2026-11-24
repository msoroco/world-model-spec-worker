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
from audit import audit
from prove import BRANCHES

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

    def test_source_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b = base / "probe_a", base / "probe_b"
            a.mkdir()
            b.mkdir()
            result = audit(make_source(a, "probe_a"), make_source(b, "probe_b"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["outside_documented_response_frames"], [0, 200])

    def test_every_statutory_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            for branch, policy in BRANCHES.items():
                base = Path(temp) / branch
                base.mkdir()
                result = measure(*make_source(base, branch))
                self.assertEqual(result["siren_observed_frames"], 200 if policy["siren"] else 0)
                self.assertEqual(result["warning_lamp_observed_frames"], 250 if policy["lamp"] else 0)
                self.assertEqual(result["siren_outside_documented_response_frames"],
                                 200 if branch == "probe_b" else 0)
                self.assertIsNone(result["physical_legal_verdict"])
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    cases = []
    root_config = json.loads((NATIVE / "config.json").read_text())
    policies = {
        "probe_a": (True, False, True),
        "probe_b": (False, False, True),
        "pursuit": (False, True, True),
        "call_lamps_only": (True, False, False),
        "ordinary_lamps_only": (False, False, False),
    }
    for probe, (call, pursuit, siren) in policies.items():
        case_id = HERE.name + "__" + probe
        config = dict(root_config, case_id=case_id,
                      emergency_call_requested=call,
                      immediate_pursuit_requested=pursuit,
                      siren_requested=siren)
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        files.extend({"path": name, "content": (NATIVE / name).read_text()}
                     for name in ("runner.py", "measure.py", "prove.py", "audit.py"))
        files.append({"path": "tests/test_source.py", "content": TEST})
        construction = {
            "case_id": case_id, "cell_id": "C109028", "law_id": "NRS-484D-400-5",
            "actor": "emergency_vehicle_driver", "entrypoint": "runner.py",
            "status": "unselected_cpu_diagnostic", "files": files,
            "recording_description": "Thirty-second emergency approach source contract; siren acoustics, authorization and original Native state unverified."}
        path = HERE / "draft-candidates" / probe / "primary" / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + "\n")
        cases.append({"case_id": case_id, "kind": "draft_not_selected",
                      "construction": str(path.relative_to(HERE)),
                      "construction_sha256": sha(path),
                      "measurement_contract": str((path.parent.parent / "measurement-contract.json").relative_to(HERE)),
                      "candidates": []})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name, "status": "draft_not_selected",
                "cases": cases, "original_native_observed": False,
                "delivery_ready": False}
    (HERE / "draft-execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()["cases"])}))
