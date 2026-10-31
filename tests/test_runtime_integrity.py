"""A manifest cannot make omitted imports or worker skills disappear."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


class RuntimeIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ROOT / 'runtime/pipeline', self.root / 'runtime/pipeline')
        shutil.copytree(ROOT / 'skills', self.root / 'skills')
        shutil.copyfile(ROOT / 'runtime.py', self.root / 'runtime.py')
        shutil.copyfile(ROOT / 'batch.json', self.root / 'batch.json')

    def run_verify(self):
        return subprocess.run(
            [sys.executable, str(self.root / 'runtime.py'), 'verify', '--runtime',
             str(self.root / 'runtime/pipeline')],
            cwd=self.root, capture_output=True, text=True, timeout=60,
        )

    def refreeze_manifest(self, *, removed=(), added=()):
        manifest_path = self.root / 'runtime/pipeline/SOURCE-MANIFEST.json'
        manifest = json.loads(manifest_path.read_text())
        for relative in removed:
            manifest['files'].pop(relative)
        for relative in added:
            manifest['files'][relative] = digest(self.root / 'runtime/pipeline' / relative)
        write(manifest_path, manifest)
        batch_path = self.root / 'batch.json'
        batch = json.loads(batch_path.read_text())
        batch['runtime']['source_manifest_sha256'] = digest(manifest_path)
        write(batch_path, batch)

    def test_current_runtime_is_closed(self):
        result = self.run_verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"runtime_sources_verified": true', result.stdout)

    def test_missing_modules_fail_even_if_manifest_is_refrozen(self):
        for name in ('intentions.py', 'trace_json.py'):
            with self.subTest(name=name):
                path = self.root / 'runtime/pipeline/scenario_pipeline' / name
                path.unlink()
                self.refreeze_manifest(removed=['scenario_pipeline/' + name])
                result = self.run_verify()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Missing required local module', result.stderr)
                shutil.copyfile(ROOT / 'runtime/pipeline/scenario_pipeline' / name, path)
                self.refreeze_manifest(added=['scenario_pipeline/' + name])

    def test_missing_worker_skill_fails(self):
        (self.root / 'skills/law-relevance-mapping/SKILL.md').unlink()
        result = self.run_verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing or changed frozen worker skill', result.stderr)

    def test_new_unresolved_import_fails(self):
        relative = 'scenario_pipeline/unknown_import_probe.py'
        (self.root / 'runtime/pipeline' / relative).write_text(
            'from missing_worker_local_module import value\n')
        self.refreeze_manifest(added=[relative])
        result = self.run_verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unresolved portable Python import', result.stderr)


if __name__ == '__main__':
    unittest.main()
