import json
from pathlib import Path
import shutil
import tempfile
import unittest

from runner import check


class SelectedSourceBinding(unittest.TestCase):
    def test_original_bundle(self):
        result = check(Path.cwd())
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['native_executed'])

    def test_changed_source_and_temporal_request_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            for name in ('config.json', 'assignment-source.json', 'road.xodr'):
                shutil.copyfile(name, bundle / name)
            (bundle / 'road.xodr').write_text('<OpenDRIVE/>\n')
            with self.assertRaisesRegex(ValueError, 'Changed source'):
                check(bundle)
            shutil.copyfile('road.xodr', bundle / 'road.xodr')
            config = json.loads((bundle / 'config.json').read_text())
            config['requested_left_interval'] = [1, 2]
            (bundle / 'config.json').write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'lateral request'):
                check(bundle)


if __name__ == '__main__':
    unittest.main()
