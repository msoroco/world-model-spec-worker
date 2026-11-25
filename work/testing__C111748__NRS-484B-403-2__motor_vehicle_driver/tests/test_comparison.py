import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison_audit', ROOT / 'comparison_audit.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
BASE = 'testing__C111748__NRS-484B-403-2__motor_vehicle_driver__'


def packet(suffix, prohibited, turn):
    display = 'no-u' if prohibited else 'other'
    return {'case_id': BASE + suffix, 'actor': 'motor_vehicle_driver', 'map_sha256': 'map',
            'route_sha256': 'route', 'highway_status': {'source_sha256': 'highway'}, 'ego_id': 42,
            'camera_plan_sha256': 'cameras', 'duration_s': 0.2,
            'device': {'device_id': 77, 'authority_source_sha256': 'authority',
                       'legal_consistency_source_sha256': 'legal', 'display_source_sha256': display,
                       'governed_approach': 'A', 'prohibits_u_turn': prohibited},
            'frames': [{'frame': i, 'time_s': i / 20,
                        'ego': {'id': 42, 'road_id': 1, 'lane_id': -1 if turn and i == 3 else 1,
                                'x': i, 'y': 0, 'yaw_deg': 180 if turn and i == 3 else 0,
                                'approach_id': 'A', 'u_turn_in_progress': turn and i == 2},
                        'device_readback': {'device_id': 77, 'prohibits_u_turn': prohibited, 'visible_to_ego': i >= 1}}
                       for i in range(4)]}


class Tests(unittest.TestCase):
    def sources(self, packets):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        out=[]
        for i,p in enumerate(packets):
            raw=json.dumps(p).encode(); path=Path(tmp.name)/(str(i)+'.json'); path.write_bytes(raw)
            out.append((path,p['case_id'],hashlib.sha256(raw).hexdigest()))
        return out
    def test_obedience_positive(self):
        src=self.sources([packet('prohibited_obey',True,False),packet('prohibited_attempt',True,True)])
        self.assertTrue(mod.audit('device_obedience',src)['declared_difference_observed'])
    def test_applicability_positive(self):
        src=self.sources([packet('prohibited_attempt',True,True),packet('neutral_device_turn',False,True)])
        self.assertTrue(mod.audit('device_applicability',src)['fixed_conditions_checked'])
    def test_reject_fixed_route_change(self):
        a=packet('prohibited_obey',True,False); b=packet('prohibited_attempt',True,True); b['route_sha256']='other'
        with self.assertRaisesRegex(mod.ComparisonError,'fixed route'):
            mod.audit('device_obedience',self.sources([a,b]))
    def test_reject_missing_action_difference(self):
        a=packet('prohibited_obey',True,False); b=packet('prohibited_attempt',True,False)
        with self.assertRaisesRegex(mod.ComparisonError,'action did not differ'):
            mod.audit('device_obedience',self.sources([a,b]))
    def test_reject_stale_native_source(self):
        src=self.sources([packet('prohibited_obey',True,False),packet('prohibited_attempt',True,True)])
        p,c,h=src[1]; p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash'):
            mod.audit('device_obedience',src)
    def test_production_cli_rejects_source_only_comparison(self):
        src=self.sources([packet('prohibited_obey',True,False),packet('prohibited_attempt',True,True)])
        command=[sys.executable,str(ROOT/'comparison_audit.py'),'--comparison','device_obedience']
        for path,case,digest in src:
            command.extend(['--source',str(path),case,digest])
        command.extend(['--output',str(Path(src[0][0]).parent/'comparison.json')])
        completed=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(completed.returncode,0)
        self.assertIn('production comparison needs two original attempts',completed.stderr)
    def test_production_pair_rejects_missing_delivery_attempt(self):
        src=self.sources([packet('prohibited_obey',True,False),packet('prohibited_attempt',True,True)])
        with self.assertRaisesRegex(ValueError,'saved source manifest missing'):
            mod.audit_attempts('device_obedience',[(p,c) for p,c,_ in src])
