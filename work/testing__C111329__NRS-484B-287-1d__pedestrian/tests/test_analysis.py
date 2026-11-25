import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze
from native_acquisition import acquire, save
from native_crossing import digest
from saved_media_audit import inventory_camera_sources
from test_saved_process import PNGAdapter, site


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = site()
        self.case = ROOT.name + '__diagonal_authorized'
        packet = acquire(PNGAdapter(), site=self.site, site_sha256=digest(self.site),
                         case_id=self.case, route_kind='opposite', authorization=True,
                         blueprint_id='walker.pedestrian.0001', frames=3,
                         capture_root=self.root)
        (self.root / 'site.json').write_text(json.dumps(self.site) + '\n')
        save(self.root / 'native-acquisition.json', packet)
        camera = inventory_camera_sources(packet, self.root)
        (self.root / 'camera-manifest.json').write_text(json.dumps(camera) + '\n')
        def ref(name):
            return {'path': name, 'sha256': hashlib.sha256((self.root / name).read_bytes()).hexdigest()}
        declaration = {'format': 'c111329-original-source-v1', 'case_id': self.case,
                       'diagnostic_fixture': True, 'site_ref': ref('site.json'),
                       'native_acquisition_ref': ref('native-acquisition.json'),
                       'camera_manifest_ref': ref('camera-manifest.json')}
        (self.root / 'pedestrian-source.json').write_text(json.dumps(declaration) + '\n')
        construction = json.loads((ROOT / 'construction-diagonal_authorized.json').read_text())
        config = next(item['content'] for item in construction['files'] if item['path'] == 'config.json')
        (self.root / 'config.json').write_text(config)

    def tearDown(self):
        self.temp.cleanup()

    def test_source_bound_measurement_and_changed_source(self):
        report = analyze(self.root, self.root / 'analysis-report.json', report_only=True)
        self.assertEqual(report['case_id'], self.case)
        self.assertEqual(report['measurements']['exception_context']['value']['NRS_484B_290_exception'], 'unresolved')
        self.assertGreater(report['measurements']['crossing_route']['value']['observed_inside_frames'], 0)
        (self.root / 'site.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'digest changed'):
            analyze(self.root, self.root / 'analysis-report.json', report_only=True)


if __name__ == '__main__':
    unittest.main()
