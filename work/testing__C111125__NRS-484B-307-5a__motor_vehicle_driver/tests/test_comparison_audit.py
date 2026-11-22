import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('arrow_comparison',ROOT/'comparison_audit.py')
audit_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_module)


def record(suffix,occupied=False):
    return {'law_id':'NRS-484B-307-5a','cell_id':'C111125','actor_id':'ego',
            'case_id':ROOT.name+'__'+suffix,'map_sha256':'map','route_sha256':'route',
            'intersection_geometry_sha256':'geometry','camera_contract_sha256':'cameras',
            'duration_s':30,
            'measurement':{'format':'worker-straight-arrow-measurements',
                           'sources':{name:'hash' for name in (
                               'signal-head-history.jsonl','ego-body-history.jsonl',
                               'participant-history.jsonl','intersection-context.json')},
                           'first_sole_arrow_frame':100,
                           'first_ego_intersection_entry_frame':120,
                           'entry_without_verified_arrow_frames':[],
                           'observed_heading_change_deg':0,
                           'lawfully_occupied_frames':[{'frame':100}] if occupied else [],
                           'ego_past_stop_line_during_occupancy_frames':[]}}


class ComparisonTests(unittest.TestCase):
    def test_accepts_only_source_bound_controlled_difference(self):
        clear=record('clear_straight');occupied=record('yield_straight',True)
        self.assertTrue(audit_module.audit(clear,occupied)['passed'])
        for key,value in [('route_sha256','other'),('camera_contract_sha256',None)]:
            changed=dict(occupied,**{key:value})
            with self.assertRaises(ValueError):audit_module.audit(clear,changed)
        changed=record('yield_straight',False)
        with self.assertRaises(ValueError):audit_module.audit(clear,changed)
        changed=record('yield_straight',True)
        changed['measurement']['ego_past_stop_line_during_occupancy_frames']=[110]
        with self.assertRaises(ValueError):audit_module.audit(clear,changed)
        changed=record('yield_straight',True)
        changed['measurement']['sources'].pop('signal-head-history.jsonl')
        with self.assertRaises(ValueError):audit_module.audit(clear,changed)


if __name__=='__main__':unittest.main()
