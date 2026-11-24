"""Bind exact selected C125751 constructions without claiming unfinished proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SUFFIXES = ('precedence','advance','timing_below','timing_inside','timing_above')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(seal_offline=False):
    draft = json.loads((HERE/'execution-manifest.draft.json').read_text())
    expected = {AID+'__'+suffix for suffix in SUFFIXES}
    if {row['case_id'] for row in draft['cases']} != expected:
        raise ValueError('Selected manifest needs all five exact cases')
    rows=[]
    for row in draft['cases']:
        case = row['case_id']
        suffix = case.removeprefix(AID+'__')
        construction = HERE/row['construction']
        contract = HERE/row['measurement_contract']
        if sha(construction) != row['construction_sha256'] or sha(contract) != row['measurement_contract_sha256']:
            raise ValueError('Selected construction or measurement contract changed')
        entry = {'case_id':case, 'kind':'delivery',
                 'construction':construction.name, 'construction_sha256':sha(construction),
                 'measurement_contract':contract.name,
                 'measurement_procedure':{'entrypoint':'analysis.py'},
                 'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                   'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT',
                                   'survey_env_var':'C125751_SURVEY',
                                   'survey_sha256_env_var':'C125751_SURVEY_SHA256',
                                   'map_source_env_var':'C125751_MAP_SOURCE'},
                 'candidate_risk':row['candidate_risk'], 'candidates':[],
                 'missing_proofs':['source-shaped positive and negative compatibility',
                                   'saved-only processing and physical audit lifecycle',
                                   'source-reviewed production actor, controller and mount packet']}
        if seal_offline:
            log = HERE/('cpu-selected-offline-'+suffix+'.log')
            if not log.is_file() or 'offline_passed' not in log.read_text():
                raise ValueError('Exact selected offline check missing: '+suffix)
            command = ('.venv-cpu/bin/python runtime.py offline --manifest '
                       f'work/{AID}/execution-manifest.json --case {case} '
                       f'--output .runtime-work/c125751-selected-offline-v15-{suffix} '
                       '--python "$PWD/.venv-cpu/bin/python"')
            entry['offline'] = {'command':command, 'exit_code':0,
                                'construction_sha256':sha(construction),
                                'log':log.name, 'log_sha256':sha(log)}
        else:
            entry['offline'] = {'status':'pending selected-manifest run'}
        rows.append(entry)
    manifest = {'format':'worker-execution-manifest', 'assignment_id':AID,
                'runtime_manifest_sha256':sha(REPO/'runtime'/'SOURCE-MANIFEST.json'),
                'status':'partial_selected_delivery',
                'cases':rows}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('bound five selected delivery entries; unfinished proofs remain explicit')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--seal-offline',action='store_true')
    build(parser.parse_args().seal_offline)
