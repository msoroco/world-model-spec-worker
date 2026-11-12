"""Build an isolated 8.5 m exact case and three candidate constructions.

The selected eight-case manifest is not changed until all exact CPU proofs pass.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
NEW = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_midpoint'
OUT = ROOT/'midpoint-draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((ROOT/'execution-manifest.json').read_text())
    base = next(x for x in selected['cases'] if x['case_id'] == OLD)
    case = copy.deepcopy(base)
    case['case_id'] = NEW
    case['candidate_risk'] = {'status':'physical',
        'reason':'hill-crest lead visibility and lane-change timing require original Native review'}
    for key in ('offline','compatibility','post_capture','physical_preparation','delivery_acceptance','negative'):
        case.pop(key, None)
    OUT.mkdir(exist_ok=True)
    for suffix, row in [('primary',case), *[(x['id'],x) for x in case['candidates']]]:
        source = ROOT/f'body-geometry-draft/all/source_verified_base-{suffix}.json'
        construction = json.loads(source.read_text())
        if construction['case_id'] != OLD:
            raise ValueError('Base exact construction changed')
        construction['case_id'] = NEW
        config_row = next(x for x in construction['files'] if x['path']=='config.json')
        config = json.loads(config_row['content'])
        if config['selected_case_id'] != OLD or config['requested_engineering_gap_m'] != 10.0:
            raise ValueError('Base engineering gap changed')
        config['selected_case_id'] = NEW
        config['supported_case_ids'] = [NEW if x == OLD else x for x in config['supported_case_ids']]
        config['requested_engineering_gap_m'] = 8.5
        config_row['content'] = json.dumps(config, indent=2)+'\n'
        for file in construction['files']:
            if file['path'] in ('runner.py','finalizer.py','tests/test_bundle.py'):
                file['content'] = file['content'].replace(OLD,NEW)
            if OLD in file['content']:
                raise ValueError('Old case identity remains in '+file['path'])
            if file.get('source') and (REPO/file['source']).read_text()!=file['content']:
                source=OUT/'sources'/suffix/file['path']
                source.parent.mkdir(parents=True,exist_ok=True)
                source.write_text(file['content'])
                file['source']=str(source.relative_to(REPO))
        path = OUT/f'source_verified_midpoint-{suffix}.json'
        path.write_text(json.dumps(construction,indent=2)+'\n')
        row['construction'] = str(path.relative_to(ROOT))
        row['construction_sha256'] = sha(path)
        for key in ('offline','compatibility','post_capture'):
            row.pop(key,None)
        if row.get('id') == 'fallback2':
            if 'ego_target_speed_mps' not in row['changed_knobs']:
                raise ValueError('Fallback speed trigger changed')
        print(suffix,row['construction_sha256'])
    draft = {'format':selected['format'], 'assignment_id':selected['assignment_id'],
             'runtime_manifest_sha256':selected['runtime_manifest_sha256'],
             'cases':[case]}
    (ROOT/'midpoint-draft-manifest.json').write_text(json.dumps(draft,indent=2)+'\n')


if __name__=='__main__':
    main()
