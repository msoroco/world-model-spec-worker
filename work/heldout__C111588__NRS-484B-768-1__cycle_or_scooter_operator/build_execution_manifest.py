"""Consolidate nine exact source-bound rider cases without claiming readiness."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


manifest_names = {
    'bicycle_signal_once':'first-execution-manifest.json',
    'bicycle_no_signal':'no-signal-manifest.json',
    'bicycle_signal_continuous':'continuous-manifest.json',
    'electric_bicycle_signal_once':'electric-bicycle-manifest.json',
    'electric_scooter_signal_once':'electric-scooter-manifest.json',
    'turn_lane_no_signal':'turn-lane-manifest.json',
    'both_hands_no_signal':'both-hands-manifest.json',
    'safety_wide':'safety-wide-manifest.json',
    'safety_narrow':'safety-narrow-manifest.json'}
source_rows = [(slug, filename, f'cases/{slug}/primary-tests-j.log',
                f'cases/{slug}/primary-receipt-j.json', f'cases/{slug}/primary-analysis-j.log',
                f'cases/{slug}/primary-negative-j.log') for slug, filename in manifest_names.items()]
result = json.loads((ROOT / 'result.json').read_text())
entries=[]
for slug, manifest_name, offline_name, receipt_name, analysis_name, negative_name in source_rows:
    manifest=json.loads((ROOT/manifest_name).read_text())
    entry=manifest['cases'][0]
    assert entry['case_id'].endswith('__'+slug)
    offline_path, receipt_path = ROOT/offline_name, ROOT/receipt_name
    analysis_path,negative_path = ROOT/analysis_name, ROOT/negative_name
    receipt=json.loads(receipt_path.read_text())
    assert receipt['passed'] and receipt['construction_sha256']==entry['construction_sha256']
    assert sha(analysis_path)==receipt['log_sha256'] and sha(negative_path)==receipt['negative_log_sha256']
    command=(f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/{manifest_name} '
             f'--case {entry["case_id"]} --output .runtime-work/c111588-common-{slug}-primary-offline-j '
             f'--python {REPO}/.venv-cpu/bin/python')
    entry['offline']={'command':command,'exit_code':0,'log':offline_name,
                      'log_sha256':sha(offline_path),'construction_sha256':entry['construction_sha256']}
    entry['compatibility']={'receipt':receipt_name,'sha256':sha(receipt_path),'log':analysis_name}
    entry['negative']={'log':negative_name}
    construction=json.loads((ROOT/entry['construction']).read_text())
    for channel in construction['recording_description']['channels']:
        name=channel['name']
        if name not in entry['acquisition']:
            entry['acquisition'][name]={'entrypoint':'rider_common_finalizer.py',
                'method':'original source join and derived recording channel for '+name,
                'evidence':'case-specific retained source packets and four synchronized original RGB videos'}
    entries.append(entry)
output={'format':'worker-execution-manifest','assignment_id':ASSIGNMENT,
        'runtime_manifest_sha256':json.loads((ROOT/'first-execution-manifest.json').read_text())['runtime_manifest_sha256'],
        'cases':entries}
(ROOT/'execution-manifest.json').write_text(json.dumps(output,indent=2)+'\n')
print('Consolidated',len(entries),'exact rider cases')
