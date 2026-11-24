"""Positive and resealed negative comparison checks for exception diagnostics."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from exception_comparison_audit import compare
import exception_comparison_audit
from delivery_audit import observed_left_turn


class ExceptionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path('.runtime-work/c125714-exceptions/comparison-sources').resolve()
        if not self.scratch.is_dir():
            self.skipTest('materialized source-only diagnostics unavailable')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for kind in ('timing_inside_training','official_device_controlled',
                     'opposite_intends_left','opposite_makes_left'):
            shutil.copytree(self.scratch/kind,self.root/kind)

    def reseal(self,kind,name):
        path=self.root/kind/name
        binding=self.root/kind/'original-bindings.json'
        data=json.loads(binding.read_text())
        data[name]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        binding.write_text(json.dumps(data)+'\n')

    def test_both_exact_comparisons(self):
        for comparison in ('device_governance_exception','opposite_turn_realization'):
            result=compare(self.root,comparison)
            self.assertTrue(result['fixed_conditions_verified'])
            self.assertEqual(result['legal_exception_applies'],'unresolved')

    def test_resealed_fixed_crossing_change_rejected(self):
        kind='official_device_controlled';path=self.root/kind/'site-context.json'
        data=json.loads(path.read_text());data['crossing_id']='another crossing'
        path.write_text(json.dumps(data)+'\n');self.reseal(kind,'site-context.json')
        with self.assertRaisesRegex(ValueError,'fixed exception comparison context'):
            compare(self.root,'device_governance_exception')

    def test_resealed_missing_original_turn_rejected(self):
        kind='opposite_makes_left';path=self.root/kind/'other-body-history.jsonl'
        rows=[json.loads(row) for row in path.read_text().splitlines()]
        for row in rows[40:]:
            row['body_vertices_xy_m']=[[x-10,y+14] for x,y in row['body_vertices_xy_m']]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        self.reseal(kind,'other-body-history.jsonl')
        with self.assertRaisesRegex(ValueError,'declared original left-turn difference'):
            compare(self.root,'opposite_turn_realization')

    def test_turn_observation_uses_reviewed_crossing_position(self):
        other = [json.loads(row) for row in
                 (self.root/'opposite_makes_left/other-body-history.jsonl').read_text().splitlines()]
        translated = []
        for row in other:
            row = dict(row, body_vertices_xy_m=[
                [x+100,y+200] for x,y in row['body_vertices_xy_m']])
            translated.append(row)
        polygon = [[95,195],[105,195],[105,205],[95,205]]
        self.assertTrue(observed_left_turn(translated,polygon))

    def test_original_mode_checks_release_schedule_after_source_audit(self):
        for kind in ('timing_inside_training','official_device_controlled'):
            folder=self.root/kind
            site_path=folder/'site-context.json';site=json.loads(site_path.read_text())
            scene=json.loads((ROOT/'cases'/kind/'scene.json').read_text())
            site['ego_route_xyz_m']=scene['ego_route_xyz_m']
            site['other_route_xyz_m']=scene['other_route_xyz_m']
            site_path.write_text(json.dumps(site)+'\n')
            control=[{'frame':i,'time_s':i/20,'ego_release_s':.975,
                      'other_release_s':1.0,'ego_brake':0}
                     for i in range(75)]
            (folder/'controller-history.jsonl').write_text(''.join(
                json.dumps(row)+'\n' for row in control))
            old=json.loads((folder/'original-bindings.json').read_text())
            old['site-context.json']['sha256']=hashlib.sha256(site_path.read_bytes()).hexdigest()
            for name in ('video_frames.jsonl','controller-history.jsonl'):
                old[name]={'kind':'original_native','sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest()}
            for item in old.values():item['kind']='original_native'
            (folder/'source-manifest.json').write_text(json.dumps(old)+'\n')
            (folder/'original-bindings.json').unlink()
        with patch.object(exception_comparison_audit,'audit_sources',return_value={'frames':75}):
            self.assertFalse(compare(self.root,'device_governance_exception')['diagnostic_fixture'])
            path=self.root/'official_device_controlled/controller-history.jsonl'
            data=[json.loads(row) for row in path.read_text().splitlines()]
            data[0]['ego_release_s']=2.0
            path.write_text(''.join(json.dumps(row)+'\n' for row in data))
            with self.assertRaisesRegex(ValueError,'fixed original release schedule'):
                compare(self.root,'device_governance_exception')
