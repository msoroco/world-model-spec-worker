"""Independent raw-source check of the controlled passing diagnostic pair."""
import importlib.util
import json
from pathlib import Path
import statistics
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from passing_carveout import measure

spec=importlib.util.spec_from_file_location('fixture',HERE/'prove-passing-carveout.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
roots={key:fixture.write_case(key=='pass') for key in ('hold','pass')}
values={key:measure(root) for key,root in roots.items()}
rows={key:[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
      for key,root in roots.items()}
if any(len(sample)!=480 for sample in rows.values()):raise AssertionError('Frame count')
for index,(hold,passing) in enumerate(zip(rows['hold'],rows['pass'])):
    if any(hold['lead'][key]!=passing['lead'][key] for key in ('body_xy_m','speed_mps','lane_id')):
        raise AssertionError('Lead actor changed across controlled pair')
    if index==0 and hold['ego']['body_xy_m']!=passing['ego']['body_xy_m']:
        raise AssertionError('Initial ego position changed across pair')
    if hold['ego']['lane_id']!=-1 or hold['opposing_lane_actors']!=[] or passing['opposing_lane_actors']!=[]:
        raise AssertionError('Controlled lane or opposing source differs')
pass_rows=rows['pass']
first,last=pass_rows[0],pass_rows[-1]
def center(actor):return statistics.mean(point[0] for point in actor['body_xy_m'])
if not center(first['ego'])<center(first['lead'])-12 or \
        not center(last['ego'])>center(last['lead'])+12 or \
        first['ego']['lane_id']!=-1 or last['ego']['lane_id']!=-1:
    raise AssertionError('Independent follow/pass/return sequence differs')
opposing=sum(row['ego']['lane_id']==1 for row in pass_rows)
if opposing!=values['pass']['opposing_lane_frames'] or opposing<200:
    raise AssertionError('Independent opposing-lane exposure differs')
if values['hold']['passing_sequence_observed'] or not values['pass']['passing_sequence_observed']:
    raise AssertionError('Passing classification differs')
print(json.dumps({'passed':True,'frames_per_case':480,'lead_trace_fixed':True,
    'opposing_lane_frames':opposing,'physical_or_legal_verdict_claim':False},sort_keys=True))
