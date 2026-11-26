import json
import unittest
from pathlib import Path

from median_scene import check


class MedianRequestTest(unittest.TestCase):
    def test_exact_bundle(self):
        folder = Path.cwd()
        request = json.loads((folder/'request.json').read_text())
        config = json.loads((folder/'config.json').read_text())
        self.assertEqual(check(request)['case'], config['case_id'].rsplit('__', 1)[-1])


if __name__ == '__main__':
    unittest.main()
