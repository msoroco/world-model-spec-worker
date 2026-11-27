"""Saved-only source-bound width finalizer protocol tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import build, save_result
from native_capture import capture
from test_native_capture import Operator
from width_measurement import ASSIGNMENT


class SavedAnalysisTests(unittest.TestCase):
    def make_attempt(self,root):
        case_id=ASSIGNMENT+'__width_9_9ft'
        actor=Operator(case_id)
        attempt=root/'attempt';attempt.mkdir()
        capture(actor,case_id,attempt/'original-attempt')
        (attempt/'config.json').write_text(json.dumps({'selected_case_id':case_id,
            'variant':'width_9_9ft','target_width_ft':9.9})+'\n')
        names=('qualifying_other_alley','local_ordinance_applicability',
            'original_vehicle_footprints','alley_cross_sections',
            'available_continuous_width_ft','parking_activity',
            'free_vehicular_movement','four_view_frame_join')
        (attempt/'construction.json').write_text(json.dumps({'recording_description':{
            'channels':[{'name':name,'unit':'structured'} for name in names],
            'context_inputs':[{'name':'reviewed_alley_width_packet','unit':'source'}]}})+'\n')
        plan=json.loads((Path(__file__).resolve().parents[1]/'case-plan.json').read_text())
        (attempt/'case-plan.json').write_text(json.dumps(plan)+'\n')
        original=json.loads((attempt/'original-attempt'/'frame_map.json').read_text())['frames']
        with (attempt/'video_frames.jsonl').open('w') as stream:
            for row in original:
                stream.write(json.dumps({'video_frame':row['video_frame'],
                    'carla_frame':row['frame'],'time_s':row['time_s']})+'\n')
        with (attempt/'trace.jsonl').open('w') as stream:
            for row in original:stream.write(json.dumps({'frame':row['frame']})+'\n')
        for view in ('overview','approach','reference_corner','driver_reference'):
            (attempt/(view+'.mkv')).write_bytes(b'diagnostic-placeholder')
        (attempt/'fixture-provenance.json').write_text(json.dumps({
            'diagnostic_fixture':True,'physical_acceptance_claimed':False})+'\n')
        return attempt

    def test_saved_finalizer_uses_original_width(self):
        scratch=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=scratch) as td:
            attempt=self.make_attempt(Path(td))
            built=build(attempt)
            result=save_result(attempt,built)
            self.assertIn('available_continuous_width_ft',result['realized_observables'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertTrue((attempt/'channels'/'available_continuous_width_ft.jsonl').exists())

    def test_missing_original_width_source_rejected(self):
        scratch=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=scratch) as td:
            attempt=self.make_attempt(Path(td))
            (attempt/'original-attempt'/'width_history.json').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):build(attempt)


if __name__=='__main__':unittest.main()
