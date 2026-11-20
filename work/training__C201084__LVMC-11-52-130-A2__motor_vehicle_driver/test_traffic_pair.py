"""CPU proof of the common-destination optional-lead Native construction."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from test_exception_probe import environment
from traffic_pair_capture import acquire
from traffic_pair_controller import request
from traffic_pair_runner import run
from traffic_pair_entrypoint import TUNINGS

HERE = Path(__file__).resolve().parent


class TrafficPairTests(unittest.TestCase):
    def survey(self, mode):
        suffix = 'near' if mode == 'near_lead' else 'absent'
        survey = json.loads((HERE/f'draft-traffic-pair-{suffix}-survey.json').read_text())
        survey['map_name'] = 'TownFireLane'
        return survey

    def test_one_destination_controller_isolates_lead_request(self):
        base = request((10,1), 0, (4,0,0), (30,1))
        lead = request((10,1), 0, (4,0,0), (30,1),
                       lead_xy_m=(18,1), lead_velocity_xyz_mps=(0,0,0))
        self.assertEqual(base['destination_xy_m'], lead['destination_xy_m'])
        self.assertEqual(base['destination_phase'], lead['destination_phase'])
        self.assertFalse(base['lead_present'])
        self.assertTrue(lead['lead_present'])
        self.assertEqual(base['control_basis'], 'common_destination_request')
        self.assertEqual(lead['control_basis'], 'observed_lead_braking_request')
        self.assertLess(base['brake'], lead['brake'])
        self.assertFalse(lead['statutory_necessity_claimed'])
        with self.assertRaisesRegex(ValueError, 'both be present or absent'):
            request((10,1), 0, (4,0,0), (30,1), lead_xy_m=(18,1))

    def test_near_and_absent_native_paths_share_capture_contract(self):
        for mode in ('near_lead','absent_lead'):
            client, carla, spawned = environment()
            seen = []
            with tempfile.TemporaryDirectory() as tmp:
                def capture(world, carla, ego, follower, lead, sign, plan, attempt):
                    self.assertEqual(plan['traffic_pair']['destination_xy_m'], [30,1])
                    self.assertEqual(plan['capture_frames'], 600)
                    self.assertEqual(len(plan['camera_names']), 4)
                    self.assertEqual(lead is not None, mode == 'near_lead')
                    self.assertFalse(plan['traffic_pair']['statutory_necessity_verified'])
                    seen.append(True)
                    return {'source_frames':600}
                result = run(client, carla, self.survey(mode), mode,
                             Path(tmp)/'attempt', acquisition=capture,
                             processor=lambda _: {
                                 'lead_present':mode == 'near_lead',
                                 'physical_or_legal_completion_claimed':False,
                                 'statutory_necessity_verified':False})
                self.assertEqual(result['mode'],mode)
                self.assertTrue((Path(tmp)/'attempt'/'native-survey-readback.json').is_file())
                self.assertTrue((Path(tmp)/'attempt'/'acquisition-provenance.json').is_file())
            self.assertEqual(seen,[True])
            self.assertEqual(spawned.count('destroy'),3 if mode == 'near_lead' else 2)

    def test_absent_mode_rejects_hidden_lead_and_short_capture(self):
        client, carla, spawned = environment()
        survey = self.survey('absent_lead')
        survey['lead_spawn_xy_m']=[18,1]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'lead construction differs'):
                run(client, carla, survey, 'absent_lead', Path(tmp)/'attempt')
        self.assertEqual(spawned,[])
        plan={'capture_hz':20,'capture_frames':10,
              'camera_names':['overview','approach','reference_corner','driver_reference'],
              'traffic_pair':{'lead_present':False}}
        with self.assertRaisesRegex(ValueError, 'capture contract differs'):
            acquire(SimpleNamespace(),SimpleNamespace(),None,None,None,None,
                    plan,Path('/tmp/unused-traffic-pair'))

    def test_all_fallback_tunings_reach_native_capture(self):
        for mode in ('near_lead','absent_lead'):
            for ident in ('fallback1','fallback2','fallback3'):
                client, carla, spawned = environment()
                expected = TUNINGS[mode][ident]
                with tempfile.TemporaryDirectory() as tmp:
                    def capture(world, carla, ego, follower, lead, sign, plan, attempt):
                        self.assertEqual(plan['traffic_pair_controller_tuning'],expected)
                        self.assertEqual(plan['traffic_pair']['destination_xy_m'],[30,1])
                        self.assertEqual(lead is not None,mode=='near_lead')
                        return {'source_frames':600}
                    run(client,carla,self.survey(mode),mode,Path(tmp)/'attempt',
                        acquisition=capture,controller_tuning=expected,
                        processor=lambda _: {'lead_present':mode=='near_lead',
                            'physical_or_legal_completion_claimed':False,
                            'statutory_necessity_verified':False})
                self.assertEqual(spawned.count('destroy'),3 if mode=='near_lead' else 2)

    def test_fallback_controls_change_distinct_source_risks(self):
        def near(gap, speed, candidate):
            return request((10,1),0,(speed,0,0),(30,1),
                           lead_xy_m=(10+gap,1),
                           lead_velocity_xyz_mps=(0,0,0),
                           **TUNINGS['near_lead'][candidate])
        self.assertEqual(near(7,1,'primary')['brake'],0)
        self.assertEqual(near(7,1,'fallback1')['brake'],1)
        self.assertEqual(near(13.5,5.5,'fallback1')['brake'],0.75)
        self.assertEqual(near(13.5,5.5,'fallback2')['brake'],1)
        self.assertLess(near(20,3,'fallback3')['throttle'],
                        near(20,3,'primary')['throttle'])
        outcomes=[]
        for candidate in TUNINGS['absent_lead']:
            control=request((25,1),0,(5,0,0),(30,1),
                            **TUNINGS['absent_lead'][candidate])
            outcomes.append((control['throttle'],control['brake']))
        self.assertEqual(len(set(outcomes)),4)


if __name__ == '__main__':
    unittest.main()
