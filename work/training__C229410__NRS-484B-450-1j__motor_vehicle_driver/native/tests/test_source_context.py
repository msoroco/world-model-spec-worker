"""Authority-source and retained-original joins for the fire-station branch."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_context import FACTS,load
from measure_entrance import measure
from prove_saved import fixture


class AuthorityContextTest(unittest.TestCase):
    def write_context(self,folder):
        sources={}
        for name in FACTS:
            source=folder/(name+'.txt')
            source.write_text('synthetic cited '+name+' diagnostic\n')
            sources[name]={'path':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                           'citation':'synthetic diagnostic '+name}
        record={'format':'c229410-authority-context-v1','state':'Nevada',
                'public_highway':True,'entrance':{'x_min_m':-3,'x_max_m':3,
                'road_edge_y_m':-4,'road_side':'south'},'initial_activity':'parked',
                'exception_context':'none','fact_reviews':{name:True for name in FACTS},
                'sources':sources}
        path=folder/'manifest.json';path.write_text(json.dumps(record)+'\n')
        return path,record

    def test_cited_context_and_changed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);path,_=self.write_context(folder)
            assert load(path)['record']['public_highway'] is True
            (folder/'station_identity.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                load(path)

    def test_review_and_path_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);path,record=self.write_context(folder)
            record['fact_reviews']['driveway_entrance']=False
            path.write_text(json.dumps(record)+'\n')
            with self.assertRaisesRegex(ValueError,'review conclusion'):
                load(path)
            record['fact_reviews']['driveway_entrance']=True
            record['sources']['driveway_entrance']['path']='../other.txt'
            path.write_text(json.dumps(record)+'\n')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                load(path)

    def test_original_saved_meter_retains_authority_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);attempt=root/'attempt';fixture(attempt,3)
            authority=attempt/'authority';authority.mkdir()
            manifest,_=self.write_context(authority)
            context_path=attempt/'entrance-context.json';context=json.loads(context_path.read_text())
            context['source_kind']='original_native'
            context['authority_manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
            context['authority_source_sha256']={name:hashlib.sha256((authority/(name+'.txt')).read_bytes()).hexdigest() for name in FACTS}
            for name in FACTS:
                (authority/(name+'.source')).write_bytes((authority/(name+'.txt')).read_bytes())
            context_path.write_text(json.dumps(context)+'\n')
            self.assertEqual(measure(attempt)['stationary_min_gap_by_entrance_side_m']['same'],0)
            (authority/'highway_boundary.source').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                measure(attempt)


if __name__=='__main__':unittest.main()
