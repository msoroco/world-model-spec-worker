"""Independent exact-file audit of C110454 CPU draft diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate
from worker_exchange.measurement_contract import validate as validate_measurement


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    if manifest['runtime_manifest_sha256']!=batch['runtime']['source_manifest_sha256']:
        raise ValueError('Pinned runtime manifest changed')
    plan=json.loads((HERE/'case-plan.json').read_text())
    rows=[]
    for entry in manifest['cases']:
        validate(HERE,entry,'LVMC-11-52-130-A11','C110454',required=False,
                 require_alternate=True,candidate_count=4)
        contract=json.loads((HERE/entry['measurement_contract']).read_text())
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            selected=entry if candidate=='primary' else next(
                c for c in entry['candidates'] if c['id']==candidate)
            construction_path=HERE/selected['construction']
            if sha(construction_path)!=selected['construction_sha256']:
                raise ValueError('Construction SHA differs')
            construction=json.loads(construction_path.read_text())
            code=next(f['content'] for f in construction['files'] if f['path']=='finalize.py')
            validate_measurement(contract,plan['requirement_dispositions'],code,entry['case_id'])
            folder=construction_path.parent
            command=json.loads((folder/'command-offline.log').read_text())
            if command['offline_passed'] is not True or command['simulation_started'] is not False:
                raise ValueError('Exact offline command did not pass')
            if command['case_id']!=entry['case_id'] or command['candidate_id']!=candidate:
                raise ValueError('Offline command chose another candidate')
            log=(folder/'offline.log').read_text()
            if 'Ran 9 tests' not in log or not log.rstrip().endswith('OK'):
                raise ValueError('Exact offline unit tests incomplete')
            receipt=json.loads((folder/'diagnostic-compatibility.json').read_text())
            if receipt['format']!='worker-package-compatibility-v1' or receipt['passed'] is not True:
                raise ValueError('Pinned v1 compatibility did not pass')
            if receipt['construction_sha256']!=selected['construction_sha256'] or (
                receipt['case_id']!=entry['case_id'] or receipt['candidate_id']!=candidate):
                raise ValueError('Compatibility receipt selects another construction')
            if receipt['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']:
                raise ValueError('Compatibility runtime differs')
            checks={'actual_analysis','native_validation','mandatory_observations',
                    'lean_decoder','render','final_decode','acquisition_unchanged'}
            if not checks<=set(receipt['checks']):
                raise ValueError('Compatibility stages incomplete')
            if sha(folder/'analysis-compatibility.log')!=receipt['log_sha256']:
                raise ValueError('Compatibility analysis log changed')
            negative=(folder/'negative-analysis.log').read_text()
            if 'Missing required source: native_parking_history.json' not in negative:
                raise ValueError('Missing-source negative did not reject')
            command_lines=(folder/'compatibility.log').read_text().splitlines()
            command_result=json.loads('\n'.join(command_lines[1:]))
            if command_result['positive']!={k:v for k,v in receipt.items() if k!='fixture_manifest'} or (
                command_result['negative']['exit_code']==0):
                raise ValueError('Compatibility command report differs')
            rows.append({'case_id':entry['case_id'],'candidate':candidate,
                         'construction_sha256':selected['construction_sha256'],
                         'offline_log_sha256':sha(folder/'offline.log'),
                         'receipt_sha256':sha(folder/'diagnostic-compatibility.json'),
                         'negative_log_sha256':sha(folder/'negative-analysis.log')})
    if len(rows)!=8 or len({r['construction_sha256'] for r in rows})!=8:
        raise ValueError('Eight distinct exact candidate constructions required')
    print(json.dumps({'format':'c110454-lvmc-independent-draft-audit-v1',
        'passed':True,'candidate_count':8,'rows':rows,
        'scope':'exact CPU offline and synthetic v1 compatibility; unselected, no strict v2 or physical claim'},indent=2))


if __name__=='__main__':
    main()
