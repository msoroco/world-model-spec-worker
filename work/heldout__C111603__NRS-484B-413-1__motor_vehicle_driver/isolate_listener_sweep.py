"""Keep listener sweep draft bundles reproducible beside the nine selected cases."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'listener-sweep'
(OUT / 'proposals').mkdir(parents=True, exist_ok=True)
plan = json.loads((HERE / 'case-plan.json').read_text())
base_case = next(row for row in plan['cases'] if row['case_id'].endswith('__ped_horn_audio'))
proposal = json.loads((HERE / 'proposals/cases.json').read_text())
base_proposal = next(row for row in proposal['cases'] if row['case_id'].endswith('__ped_horn_audio'))
ids=[]
plan['cases'] = []
proposal['cases'] = []
for offset in (2,4,6):
    prefix=f'listener-{offset}m'
    case=HERE.name+f'__ped_horn_listener_{offset}m'
    ids.append(case)
    for suffix in ('construction.json','measurement-contract.json','diagnostic.json','recipe.json','manifest.json'):
        shutil.copy2(HERE / f'{prefix}-{suffix}', OUT / f'{prefix}-{suffix}')
    recipe_path=OUT / f'{prefix}-recipe.json'
    recipe=json.loads(recipe_path.read_text())
    source=str((OUT / f'{prefix}-diagnostic.json').relative_to(ROOT))
    recipe['generator']['source']=source
    recipe['sources'][0]['source']=source
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    manifest_path=OUT / f'{prefix}-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest['cases'][0]['fixture_recipe']=str(recipe_path.relative_to(ROOT))
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    row=deepcopy(base_case)
    row['case_id']=case
    row['description']=f'Route-relative {offset} m sidewalk listener engineering point'
    row['construction_status']='draft_primary_offline_compatibility_saved_tested'
    plan['cases'].append(row)
    row=deepcopy(base_proposal)
    row['case_id']=case
    row['rationale']=f'Route-relative {offset} m sidewalk listener engineering point; audibility and affected status unverified.'
    proposal['cases'].append(row)
plan['comparisons']=[{'comparison_id':'pedestrian_listener_distance', 'case_ids':ids,
    'fixed_conditions':['same turn route, horn relay policy, pedestrian type, microphone acquisition and cameras'],
    'deliberate_differences':['requested route-relative sidewalk offset 2/4/6 m; actual PCM and effect remain unresolved']}]
for row in plan['requirement_dispositions']:
    row['case_ids']=[case for case in row.get('case_ids',[]) if case in ids]
for row in plan['observations']:
    row['case_ids']=ids if row['name']=='turn_signal_observation' else []
(OUT/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
(OUT/'proposals/cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
print('Isolated listener sweep drafts',len(ids))
