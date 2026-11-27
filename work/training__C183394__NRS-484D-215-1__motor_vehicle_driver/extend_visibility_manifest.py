"""Stage exact paired visibility constructions for subsequent CPU proofs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AID = ROOT.name
CASES = ('visibility_dim', 'visibility_high')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


manifest_path = ROOT / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
source = next(e for e in manifest['cases'] if e['case_id'].endswith('__condition_a'))
measurement_source = json.loads((ROOT / 'measurement-condition_a.json').read_text())
for case in CASES:
    case_id = AID + '__' + case
    measurement_path = ROOT / ('measurement-' + case + '.json')
    measurement = deepcopy(measurement_source)
    measurement['case_id'] = case_id
    dump(measurement_path, measurement)
    entry = deepcopy(source)
    entry['case_id'] = case_id
    entry['construction'] = f'constructions/{case}/primary/construction.json'
    entry['construction_sha256'] = sha(ROOT / entry['construction'])
    entry['candidate_risk'] = {'status': 'physical',
        'reason': 'Original target range, fog rendering and shoulder placement may miss the planned source review; acceleration gain fallback retains the pair and source contract.'}
    fallback = entry['candidates'][0]
    fallback['construction'] = f'constructions/{case}/fallback1/construction.json'
    fallback['construction_sha256'] = sha(ROOT / fallback['construction'])
    fallback['trigger'] = {'source': 'original Native actor positions and forward decoded video',
        'metric': 'target_range_and_discernibility_source_quality',
        'failure_condition': 'original target is not range-identified in the forward camera or shoulder motion is incomplete'}
    fallback['changed_knobs'] = ['vehicle acceleration gain 0.20 to 0.26; fog, target geometry and beam policy held fixed']
    fallback.pop('offline', None)
    fallback.pop('compatibility', None)
    entry['fixture_recipe'] = f'work/{AID}/fixture-recipe-{case}.json'
    entry['measurement_contract'] = measurement_path.name
    for field in ('offline', 'compatibility', 'post_capture', 'delivery_acceptance',
                  'physical_preparation'):
        entry.pop(field, None)
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != case_id] + [entry]
dump(manifest_path, manifest)
print('STAGED: seven exact manifest identities; visibility proofs pending')
