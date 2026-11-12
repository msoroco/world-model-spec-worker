"""Compare C104538 original diagnostic measurements without a legal verdict."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PREFIX=HERE.name+'__'
BRANCHES={'entrance_position':('front_of_entrance','remote_reference'),
          'approach_position':('front_of_approach','remote_reference'),
          'driveway_use':('front_of_entrance','through_driveway')}

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()

def load(branch, base):
    attempt=Path(base)/f'c104538-{branch}-primary-saved-attempt-v4'
    processed=Path(base)/f'c104538-{branch}-primary-saved-proof-v4/v0001/analysis'
    config=json.loads((attempt/'config.json').read_text())
    report=json.loads((processed/'analysis-report.json').read_text())
    result=json.loads((processed/'result.json').read_text())
    case=PREFIX+branch
    if (config.get('selected_case_id')!=case or report.get('case_id')!=case or
            result.get('case_id')!=case or result.get('legal_acceptance_claimed') is not False):
        raise ValueError('Exact station comparison case identity differs')
    measurement=report['measurements']['station_reversal']
    if result['measured_values']['station_reversal']!=measurement['value']:
        raise ValueError('Station comparison result differs from saved analysis')
    for name,expected in measurement['sources'].items():
        if digest(attempt/name)!=expected:raise ValueError('Station comparison original source changed: '+name)
    return config,measurement['value'],{'config':digest(attempt/'config.json'),
            'analysis':digest(processed/'analysis-report.json'),
            'result':digest(processed/'result.json')}

def audit(comparison_id,base):
    if comparison_id not in BRANCHES:raise ValueError('Unknown C104538 comparison')
    branches=BRANCHES[comparison_id];loaded=[load(branch,base) for branch in branches]
    left,right=(item[1] for item in loaded)
    configs=[item[0] for item in loaded]
    fixed=('law_id','cell_id','actor','rate_hz','duration_s','frames','cameras')
    if any(configs[0][key]!=configs[1][key] for key in fixed):
        raise ValueError('Station comparison fixed construction condition changed')
    if configs[0]['station_survey']['station_source']!=configs[1]['station_survey']['station_source']:
        raise ValueError('Station comparison source survey changed')
    if not (left['reversal_observed'] and right['reversal_observed'] and
            left['heading_change_deg']>=150 and right['heading_change_deg']>=150):
        raise ValueError('Station comparison lacks both diagnostic reversals')
    observed={
      'entrance_position':bool(left['body_entrance_overlap_frames']) and not right['body_entrance_overlap_frames'] and left['in_front_of_entrance_observed'] and not right['in_front_of_entrance_observed'],
      'approach_position':bool(left['body_approach_overlap_frames']) and not right['body_approach_overlap_frames'],
      'driveway_use':not left['entered_driveway'] and right['entered_driveway']
    }[comparison_id]
    if not observed:raise ValueError('Selected station diagnostic difference was not measured')
    return {'format':'worker-station-comparison-proof','comparison_id':comparison_id,
            'case_ids':[PREFIX+branch for branch in branches],
            'source_hashes':{branch:item[2] for branch,item in zip(branches,loaded)},
            'fixed_conditions_checked':list(fixed)+['station_survey.station_source'],
            'observed':{branch:{'heading_change_deg':measure['heading_change_deg'],
               'entrance_overlap_frames':len(measure['body_entrance_overlap_frames']),
               'approach_overlap_frames':len(measure['body_approach_overlap_frames']),
               'driveway_entered':measure['entered_driveway']}
               for branch,(_,measure,_) in zip(branches,loaded)},
            'deliberate_difference_measured':True,
            'scope':'synthetic software diagnostic; Native station identity and purpose remain unresolved',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--comparison',required=True)
    p.add_argument('--attempt-root',default='.runtime-work');p.add_argument('--output');a=p.parse_args()
    value=audit(a.comparison,a.attempt_root)
    if a.output:Path(a.output).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'comparison_id':a.comparison,'passed':value['deliberate_difference_measured']}))
if __name__=='__main__':main()
