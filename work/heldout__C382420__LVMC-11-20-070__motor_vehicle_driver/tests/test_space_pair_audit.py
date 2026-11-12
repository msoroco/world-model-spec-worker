import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('space_pair_audit', ROOT/'space_pair_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def receipt(case, length, occupant):
    return {'passed':True,'checks':['negative_case_source'],
            'measurement_examples':{'space_at_entry':{'value':{'entry':{
                'frame':2,'region_kind':case,'signal_state':'proceed',
                'downstream_available_length_m':length,
                'first_downstream_occupant':occupant}}}}}


class PairAuditTest(unittest.TestCase):
    def test_fixed_conditions_and_missing_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('crosswalk_clear_downstream','crosswalk_blocked_downstream')
            specs = [root/(n+'.json') for n in names]
            for n,p in zip(names,specs):
                p.write_bytes((ROOT/('diagnostic-'+n+'.json')).read_bytes())
            proofs = [root/'clear-receipt.json',root/'blocked-receipt.json']
            for p,d in zip(proofs,[receipt('marked_crosswalk',16.0,None),
                                   receipt('marked_crosswalk',3.0,'standing-blocker-1')]):
                p.write_text(json.dumps(d))
            args = [*specs,*proofs]
            self.assertTrue(module.audit(*args)['passed'])
            changed = json.loads(specs[1].read_text())
            rows = [json.loads(x) for x in changed['files']['space_frames.jsonl'].splitlines()]
            rows[2]['signal_state']='stop'
            changed['files']['space_frames.jsonl']=''.join(json.dumps(x)+'\n' for x in rows)
            specs[1].write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'changed fixed ego'):
                module.audit(*args)
            specs[1].unlink()
            with self.assertRaisesRegex(ValueError,'missing comparison source'):
                module.audit(*args)


if __name__=='__main__':
    unittest.main()
