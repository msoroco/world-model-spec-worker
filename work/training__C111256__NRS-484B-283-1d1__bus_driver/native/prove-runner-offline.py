"""Validate eight case/candidate Native construction checks without CARLA."""
import copy
import json
from pathlib import Path
from engineering import CASES,CANDIDATES,parameters
from runner import check

HERE=Path(__file__).resolve().parent
base=json.loads((HERE/'config.json').read_text())
passed=0
for suffix in CASES:
    for candidate in CANDIDATES:
        config=copy.deepcopy(base)
        config.update(case_id='training__C111256__NRS-484B-283-1d1__bus_driver__'+suffix,
                      case_suffix=suffix,candidate_id=candidate,
                      knobs=parameters(suffix,candidate)['knobs'])
        result=check(config)
        if result['camera_count']!=4 or result['carla_imported'] or result['physical_walk_observed']:
            raise ValueError('Offline construction claimed original Walk evidence')
        passed+=1
rejected=0
for key,value in (('actor','motor_vehicle_driver'),('law_id','NRS-484B-283-1d2'),
                  ('duration_s',12),('candidate_id','fallback4')):
    damaged=copy.deepcopy(base);damaged[key]=value
    try:check(damaged)
    except ValueError:rejected+=1
    else:raise ValueError('Damaged case construction accepted')
print(json.dumps({'exact_case_candidate_checks':passed,'invalid_config_rejections':rejected,
                  'carla_imported':False,'physical_walk_observed':False,
                  'selected':False},sort_keys=True))
