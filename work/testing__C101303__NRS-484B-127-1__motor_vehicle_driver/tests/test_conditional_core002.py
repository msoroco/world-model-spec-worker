"""Actual selected-source regressions for conditional Core declarations, no simulator."""
import ast
import hashlib
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[3]
OWN = ROOT/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

class ConditionalCoreTests(unittest.TestCase):
    def test_exact_scope_and_unchanged_statutory_contracts(self):
        report=json.loads((OWN/'conditional-core002-review.json').read_text())
        self.assertEqual(report['counts'],{'NRS-484B-413-2':20,'NRS-484B-250-4':2})
        for row in report['changes']:
            folder=ROOT/'work'/row['assignment_id']
            manifest=json.loads((folder/'execution-manifest.json').read_text())
            entry=next(e for e in manifest['cases'] if e['case_id']==row['case_id'])
            construction=folder/entry['construction']
            bundle=json.loads(construction.read_text())
            cfg=json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
            self.assertEqual(cfg['required_atoms'],row['required_atoms_after'])
            self.assertEqual(set(row['required_atoms_before'])-set(cfg['required_atoms']),set(row['removed_required_core_atoms']))
            self.assertEqual(sha(construction),row['construction_sha256'])
            self.assertEqual(sha(ROOT/row['law_contract']),row['law_contract_sha256'])
        for path,digest in report['preserved_case_plan_hashes'].items():
            self.assertEqual(sha(ROOT/path),digest)

    def test_actual_all_twenty_analyzers_preserve_off_history_and_detect_interruption(self):
        report=json.loads((OWN/'conditional-core002-review.json').read_text())
        checked=0
        for row in report['changes']:
            if row['removed_required_core_atoms']!=['sig.turn_indicator']:
                continue
            folder=ROOT/'work'/row['assignment_id']
            manifest=json.loads((folder/'execution-manifest.json').read_text())
            entry=next(e for e in manifest['cases'] if e['case_id']==row['case_id'])
            bundle=json.loads((folder/entry['construction']).read_text())
            source=next(f['content'] for f in bundle['files'] if f['path']==entry['measurement_procedure']['entrypoint'])
            nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('approach_path','indicator_continuity')]
            namespace={}
            exec(compile(ast.Module(body=nodes,type_ignores=[]),str(folder/'analyze.py'),'exec'),namespace)
            for threshold in (100,300):
                distance=threshold*.3048
                p={'threshold_ft':threshold,'turn_onset_frame':13,'path_rows':[{'x_m':x,'y_m':0} for x in (-distance-10,-distance,-distance/2,0)],'indicator_rows':[{'frame':10+i,'lamp_bits':bit,'pixel_luminance':None} for i,bit in enumerate((False,True,True,True))]}
                self.assertEqual(namespace['approach_path'](p)['last_100ft_start_index'],1)
                out=namespace['indicator_continuity'](p)
                self.assertTrue(out['continuous_api_on'])
                self.assertFalse(p['indicator_rows'][0]['lamp_bits'])
                p['indicator_rows'][2]['lamp_bits']=False
                out=namespace['indicator_continuity'](p)
                self.assertFalse(out['continuous_api_on'])
                self.assertEqual(out['lamp_bits'],[True,False,True])
                self.assertEqual(out['original_frames'],[11,12,13])
                self.assertFalse(out['pixel_visibility_verified'])
            checked+=1
        self.assertEqual(checked,20)

if __name__=='__main__':
    unittest.main()
