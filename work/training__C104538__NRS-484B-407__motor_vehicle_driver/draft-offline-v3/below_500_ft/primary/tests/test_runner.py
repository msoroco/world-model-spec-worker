import json
import unittest
from pathlib import Path
from runner import check,control_for_time,frame_map_row

ROOT=Path(__file__).resolve().parent
if not (ROOT/'config.json').exists():ROOT=ROOT.parent


class RunnerPreflightTest(unittest.TestCase):
    def setUp(self):self.base=json.loads((ROOT/'config.json').read_text())

    def test_all_twelve_unselected_native_preflights(self):
        suffixes=(self.base['case_suffix'],) if (ROOT/'obstruction.json').exists() else (
            'below_500_ft','at_500_ft','above_500_ft')
        for suffix in suffixes:
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                with self.subTest(suffix=suffix,candidate=candidate):
                    config=dict(self.base,case_suffix=suffix,candidate_id=candidate,
                        case_id='training__C104538__NRS-484B-407__motor_vehicle_driver__'+suffix)
                    report=check(config)
                    self.assertEqual(report['camera_count'],4)
                    self.assertFalse(report['native_imported'])
                    self.assertFalse(report['physical_success_claimed'])

    def test_wrong_identity_and_capture_timing_rejected(self):
        for changed in (dict(case_suffix='invented'),dict(candidate_id='fallback4'),
                        dict(duration_s=12),dict(law_id='other')):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):check(dict(self.base,**changed))

    def test_original_frame_identity(self):
        self.assertEqual(frame_map_row(0,101,.05),
                         {'video_frame':0,'native_frame':101,'carla_frame':101,'time_s':.05})
        for values in ((-1,101,.05),(0,-1,.05),(0,101,float('nan'))):
            with self.assertRaises(ValueError):frame_map_row(*values)

    def test_reversal_controls_are_requests(self):
        class Stub:
            @staticmethod
            def VehicleControl(**values):return values
        self.assertFalse(control_for_time(Stub,5)['reverse'] if 'reverse' in control_for_time(Stub,5) else False)
        self.assertTrue(control_for_time(Stub,12)['reverse'])
        self.assertGreater(control_for_time(Stub,20)['brake'],0)


if __name__=='__main__':unittest.main()
