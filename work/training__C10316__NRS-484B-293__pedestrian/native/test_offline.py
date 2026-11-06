import json
from pathlib import Path
import tempfile
import unittest

from engineering import candidate
from fallback_triggers import measure as measure_fallback
from geometry import check as geometry_check
from measure_crosswalk import measure
from runner import cameras,check


class CrosswalkOffline(unittest.TestCase):
    def test_exact_bundle_check(self):
        config=json.loads(Path('config.json').read_text())
        result=check(config)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_success_claimed'])
        self.assertEqual(len(result['camera_names']),4)

    def test_distinct_alternatives(self):
        config=json.loads(Path('config.json').read_text())
        suffix=config['case_suffix']
        plans=[candidate(suffix,ident) for ident in ('primary','fallback1','fallback2','fallback3')]
        self.assertEqual(len({json.dumps(p['engineering'],sort_keys=True) for p in plans}),4)
        self.assertEqual(len({p['case_id'] for p in plans}),1)
        self.assertEqual([(c['width'],c['height']) for c in cameras(plans[0])],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])

    def test_authored_geometry(self):
        result=geometry_check()
        self.assertEqual(result['crosswalk_length_m'],4)
        self.assertEqual(result['crosswalk_width_m'],3)

    def test_missing_original_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            (path/'crosswalk-context.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Missing required source: native_samples.jsonl'):
                measure(path/'native_samples.jsonl',path/'crosswalk-context.json')

    def test_fallback_source_digest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'observations.jsonl'
            path.write_text('{"source_kind":"synthetic_cpu_fixture"}\n')
            with self.assertRaisesRegex(ValueError,'Changed fallback observation source'):
                measure_fallback(path,'0'*64)


if __name__=='__main__':unittest.main()
