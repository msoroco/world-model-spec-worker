import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_deferred_source_constructions import build
from build_semantic_proposals import KINDS


class DeferredSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c158208-owner-nov26b" / "tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _bundle(self, kind="nearest_view_response", candidate="primary"):
        result = build(kind, candidate)
        construction = json.loads((HERE / result["construction"]).read_text())
        bundle = self.root / (kind + "-" + candidate)
        bundle.mkdir()
        for item in construction["files"]:
            target = bundle / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"])
        (bundle / "construction.json").write_text(json.dumps(construction) + "\n")
        return bundle

    def _run(self, bundle, *args, env=None):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if env is not None:
            environment.update(env)
        environment.pop("C158208_REVIEWED_SITE", None)
        environment.pop("C158208_REVIEWED_SITE_SHA256", None)
        if env:
            environment.update(env)
        return subprocess.run([sys.executable, str(bundle / "runner.py"), *args],
                              env=environment, capture_output=True, text=True)

    def test_all_exact_source_gated_bundles_have_stable_identity(self):
        for kind in sorted(KINDS):
            for candidate, target in (("primary", 4.0), ("fallback1", 3.5)):
                with self.subTest(kind=kind, candidate=candidate):
                    bundle = self._bundle(kind, candidate)
                    result = self._run(bundle, "--check")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(HERE.name + "__" + kind, result.stdout)
                    config = json.loads((bundle / "config.json").read_text())
                    self.assertEqual(config["candidate_target_speed_mps"], target)

    def test_capture_requires_hash_bound_original_sources_before_carla(self):
        bundle = self._bundle()
        missing = self._run(bundle, "--output-dir", str(self.root / "attempt"))
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("source-hashed reviewed C158208 site required", missing.stderr)
        site = self.root / "fixture-site.json"
        site.write_text(json.dumps({"review_status": "reviewed", "cell_id": "C158208",
                                    "diagnostic_fixture": True}) + "\n")
        environment = {"C158208_REVIEWED_SITE": str(site),
                       "C158208_REVIEWED_SITE_SHA256": hashlib.sha256(site.read_bytes()).hexdigest()}
        fixture = self._run(bundle, "--output-dir", str(self.root / "attempt"), env=environment)
        self.assertNotEqual(fixture.returncode, 0)
        self.assertIn("original reviewed C158208 site required", fixture.stderr)
        site.write_text(site.read_text() + "tampered")
        stale = self._run(bundle, "--output-dir", str(self.root / "attempt"), env=environment)
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("reviewed C158208 site source bytes changed", stale.stderr)


if __name__ == "__main__":
    unittest.main()
