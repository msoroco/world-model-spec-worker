import unittest
from lane_signal_measurement import measure


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'frame': 100+i, 'time_s': i*.05, 'x': i*.25, 'y': 1.75,
                      'reported_device_state': 'off' if i < 2 else 'left'} for i in range(8)]
        self.departure = {'time_bracket_s': [.25, .30]}

    def test_original_path_integral_and_temporal_interval(self):
        self.rows[5]['y'] += .1
        expected = .5 + 2*(.25**2+.1**2)**.5
        result = measure(self.rows, self.departure)
        self.assertEqual(result['status'], 'measured')
        self.assertAlmostEqual(result['value'], expected)
        self.assertAlmostEqual(result['sampling_distance_interval_m'][0], expected-(.25**2+.1**2)**.5)
        self.assertAlmostEqual(result['sampling_distance_interval_m'][1], expected+.25)
        self.assertEqual(result['onset_time_bracket_s'], [.05,.10])

    def test_interruption_cannot_count_as_continuous_signal(self):
        self.rows[4]['reported_device_state']='off'
        result=measure(self.rows,self.departure)
        self.assertEqual(result['status'],'unavailable')
        self.assertIn('continuous',result['reason'])

    def test_gap_and_unknown_transition_remain_unavailable(self):
        self.rows[4]['frame'] += 1
        self.assertEqual(measure(self.rows,self.departure)['status'], 'unavailable')
        self.setUp(); self.rows[1]['reported_device_state'] = 'unknown'
        self.assertEqual(measure(self.rows,self.departure)['status'], 'unavailable')
        self.setUp(); self.departure['time_bracket_s'][0] = .20
        self.assertEqual(measure(self.rows,self.departure)['status'], 'unavailable')

class SavedProjectionTests(unittest.TestCase):
    def test_separate_availability_window_preserves_integration_and_originals(self):
        import json
        import tempfile
        from pathlib import Path
        from lane_signal_measurement import project_saved_measurement, METHOD, WINDOW
        rows=[{'frame':100+i,'time_s':i*.05,'x':i*.25,'y':1.75,'reported_device_state':'off' if i<2 else 'left'} for i in range(8)]
        departure={'time_bracket_s':[.25,.30]}
        measured=measure(rows,departure)
        event=measured['sample_window_s'][1]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            streams={'ego_trajectory':[], 'ego_turn_indicator':[], 'ego_course_change':[], 'ego_signal_lead_distance':[]}
            for r in rows:
                values={'ego_trajectory':{'position_local_m':{'x':r['x'],'y':r['y']},'source_frame':r['frame']},
                        'ego_turn_indicator':{'reported_device_state':r['reported_device_state']},
                        'ego_course_change':{'departure_annotation':departure if r['time_s']>=event else None},
                        'ego_signal_lead_distance':measured if r['time_s']>=event else {'status':'unavailable','value':None}}
                for name,value in values.items():streams[name].append({'time_s':r['time_s'],'value':value})
            for name,values in streams.items(): (root/(name+'.jsonl')).write_text(''.join(json.dumps(v)+'\n' for v in values))
            originals={p.name:p.read_bytes() for p in root.iterdir()}
            result={'realized_observables':{'ego_signal_lead_distance':dict(measured,reference='ego_signal_lead_distance_scalar.jsonl',integration_input_window_s=measured['sample_window_s'],sample_window_s=[event,event])},'recording_evidence':[{'name':'ego_signal_lead_distance','reference':'ego_signal_lead_distance.jsonl'}]}
            before=json.dumps(result,sort_keys=True)
            case={'sweep_id':'C245490-appropriate-signal','sweep_measurements':[{'observable':'ego_signal_lead_distance','unit':'m','measurement':{'method':METHOD,'time_window':WINDOW,'statistic':'last'}}]}
            projected,audit=project_saved_measurement(result,root,case)
            self.assertEqual(before,json.dumps(result,sort_keys=True))
            self.assertEqual(projected['recording_evidence'][0]['reference'],projected['realized_observables']['ego_signal_lead_distance']['reference'])
            self.assertEqual(projected['realized_observables']['ego_signal_lead_distance']['integration_input_window_s'],measured['sample_window_s'])
            self.assertEqual(projected['realized_observables']['ego_signal_lead_distance']['sample_window_s'],[event,event])
            self.assertEqual(originals,{name:(root/name).read_bytes() for name in originals})
            self.assertTrue(audit['original_channels_unchanged'])


class SideIndependentTests(unittest.TestCase):
 def test_right_reuses_algorithm_without_mutating_raw_states(self):
  from lane_signal_measurement import measure_for_side
  rows=[{'frame':i,'time_s':i*.05,'x':i*.25,'y':0,'reported_device_state':'off' if i<2 else 'right'} for i in range(8)]
  result=measure_for_side(rows,{'time_bracket_s':[.25,.30]},'right')
  self.assertEqual(result['status'],'measured');self.assertEqual(rows[2]['reported_device_state'],'right')
 def test_opposite_is_not_continuous_right(self):
  from lane_signal_measurement import measure_for_side
  rows=[{'frame':i,'time_s':i*.05,'x':i*.25,'y':0,'reported_device_state':'off' if i<2 else 'left'} for i in range(8)]
  self.assertEqual(measure_for_side(rows,{'time_bracket_s':[.25,.30]},'right')['status'],'unavailable')
