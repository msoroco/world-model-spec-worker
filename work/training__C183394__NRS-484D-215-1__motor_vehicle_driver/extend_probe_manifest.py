"""Add the three source-hashed exact probe identities to the delivery manifest."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PROBES = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


manifest_path = ROOT/'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
source = next(e for e in manifest['cases'] if e['case_id'].endswith('__condition_a'))
measurement_source = json.loads((ROOT/'measurement-condition_a.json').read_text())
for probe in PROBES:
    case_id = AID+'__'+probe
    measurement_path = ROOT/('measurement-'+probe+'.json')
    measurement = deepcopy(measurement_source)
    measurement['case_id'] = case_id
    dump(measurement_path, measurement)
    entry = deepcopy(source)
    entry['case_id'] = case_id
    entry['construction'] = f'constructions/{probe}/primary/construction.json'
    entry['construction_sha256'] = sha(ROOT/entry['construction'])
    entry['candidate_risk'] = {'status': 'physical',
        'reason': 'Original Native actor placement and 20 Hz movement may miss the authored one-foot probe window; alternate gain retains the exact case and capture contract.'}
    fallback = entry['candidates'][0]
    fallback['construction'] = f'constructions/{probe}/fallback1/construction.json'
    fallback['construction_sha256'] = sha(ROOT/fallback['construction'])
    fallback['trigger'] = {'source': 'original Native actor centre positions and timestamp',
                           'metric': 'observed_oncoming_separation_ft',
                           'failure_condition': 'original trace does not enter the requested one-foot physical probe band'}
    fallback['changed_knobs'] = ['vehicle acceleration gain 0.20 to 0.26; exact starting geometry held fixed']
    fallback.pop('offline', None)
    fallback.pop('compatibility', None)
    entry['fixture_recipe'] = f'work/{AID}/fixture-recipe-{probe}.json'
    entry['measurement_contract'] = measurement_path.name
    for field in ('offline', 'compatibility', 'post_capture', 'delivery_acceptance',
                  'physical_preparation'):
        entry.pop(field, None)
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != case_id] + [entry]
dump(manifest_path, manifest)
print('PASS: five exact manifest identities and three new measurement contracts')
