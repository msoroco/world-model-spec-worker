"""Check current portable runtime imports and worker dependency policy."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = json.loads((ROOT / "batch.json").read_text())
sys.path.insert(0, str(ROOT / BATCH["runtime"]["root"] / "scenario_pipeline"))
from worker_exchange.portable import validate_imports


class RuntimeImportTests(unittest.TestCase):
    def test_required_shared_modules_import(self):
        import intentions
        from worker_exchange import fixture_generator, preparation
        self.assertTrue(callable(preparation.check))
        self.assertTrue(hasattr(fixture_generator, "__file__"))
        self.assertTrue(hasattr(intentions, "__file__"))

    def test_pinned_dependencies_allowed_but_unknown_import_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            assignment = "one"
            source = repo / "work" / assignment
            inputs = repo / "inputs" / assignment
            source.mkdir(parents=True)
            inputs.mkdir(parents=True)
            (repo / "batch.json").write_text(json.dumps({"runtime": {}}))
            (inputs / "assignment.json").write_text(json.dumps({"external_imports": ["carla"]}))
            code = source / "runner.py"
            code.write_text("import numpy\nimport scenario_pipeline\n")
            validate_imports(repo, assignment)
            code.write_text("import numpy\nimport missing_not_pinned\n")
            with self.assertRaisesRegex(ValueError, "missing_not_pinned"):
                validate_imports(repo, assignment)


if __name__ == "__main__":
    unittest.main()
