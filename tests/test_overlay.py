import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import overlay


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root/'runtime/main-pipeline-v1'
        self.source = self.root/'work/_shared/runtime-overlay'
        self.output = self.root/'.runtime-work/overlay'
        old = self.base/'scenario_pipeline/traffic_spec_adapter/adapter.py'
        old.parent.mkdir(parents=True)
        old.write_text('VALUE = 1\n')
        manifest = self.base/'SOURCE-MANIFEST.json'
        manifest.write_text(json.dumps({'files':{'scenario_pipeline/traffic_spec_adapter/adapter.py':digest(old)}}))
        replacement = self.source/'scenario_pipeline/traffic_spec_adapter/adapter.py'
        replacement.parent.mkdir(parents=True)
        replacement.write_text('VALUE = 2\n')
        self.spec = {'format':'worker-runtime-overlay-v1','baseline_sha256':digest(manifest),
                     'files':[{'path':'scenario_pipeline/traffic_spec_adapter/adapter.py',
                               'baseline_sha256':digest(old),'replacement_sha256':digest(replacement)}]}
        (self.source/'overlay.json').write_text(json.dumps(self.spec))
        self.patches = [patch.object(overlay, key, value) for key,value in
                        [('ROOT',self.root),('BASELINE',self.base),('SOURCE',self.source),('OUTPUT',self.output)]]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_source_hashed_materialization(self):
        self.assertEqual(overlay.effective_runtime(),self.output)
        self.assertEqual((self.output/'scenario_pipeline/traffic_spec_adapter/adapter.py').read_text(),'VALUE = 2\n')
        self.assertEqual((self.base/'scenario_pipeline/traffic_spec_adapter/adapter.py').read_text(),'VALUE = 1\n')

    def test_changed_replacement_rejected(self):
        (self.source/'scenario_pipeline/traffic_spec_adapter/adapter.py').write_text('VALUE = 3\n')
        with self.assertRaisesRegex(ValueError,'replacement changed'):
            overlay.effective_runtime()

    def test_core_replacement_rejected(self):
        self.spec['files'][0]['path']='library/TrafficSpec/Core/Vocab/Atoms.lean'
        (self.source/'overlay.json').write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError,'outside portable'):
            overlay.effective_runtime()


if __name__ == '__main__':
    unittest.main()
