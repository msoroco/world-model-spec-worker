import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from source_channels import derive,SOURCE_NAMES

class SourceChannelTests(unittest.TestCase):
    def test_diagnostic_never_becomes_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'entrance-context.json').write_text(json.dumps({'source_kind':'synthetic_diagnostic'}))
            views=derive(p)
            self.assertEqual(set(views),set(SOURCE_NAMES))
            self.assertTrue(all(v['diagnostic_only'] and v['review_status']=='unverified' for v in views.values()))

    def test_native_requires_bound_manifest_and_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'authority').mkdir()
            manifest={'sources':{name:{'sha256':hashlib.sha256(name.encode()).hexdigest()} for name in ('station_identity','driveway_entrance','highway_boundary','activity_and_directions')}}
            (p/'authority/manifest.json').write_text(json.dumps(manifest))
            (p/'entrance-context.json').write_text(json.dumps({'source_kind':'original_native','authority_manifest_sha256':hashlib.sha256((p/'authority/manifest.json').read_bytes()).hexdigest(),'authority_source_sha256':{name:item['sha256'] for name,item in manifest['sources'].items()}}))
            for name in manifest['sources']:(p/'authority'/(name+'.source')).write_text(name)
            (p/'road.xodr').write_text('road')
            (p/'native-vehicle.jsonl').write_text(json.dumps({'traffic_conflict_vehicle':None})+'\n')
            self.assertEqual(derive(p)['police_direction_source']['review_status'],'source_record_missing')
            (p/'authority/police_direction.source').write_text('irrelevant')
            (p/'authority/station_identity.source').write_text('changed')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                derive(p)

if __name__=='__main__':unittest.main()
