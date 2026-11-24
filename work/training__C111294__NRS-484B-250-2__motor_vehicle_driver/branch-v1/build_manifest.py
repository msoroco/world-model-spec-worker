"""Bind exact selected exclusion-branch constructions for runtime CPU probes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path,obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def build():
    entries=[]
    for suffix in ('device_controlled','opposing_no_turn','opposing_left_turn'):
        case_id=BASE.name+'__'+suffix
        contract={'format':'worker-measurement-contract','case_id':case_id,
                  'requirements':[{'disposition_index':1,
                                   'requirement':'NRS-484B-250-2',
                                   'source':'NRS 484B.250(2); with 484B.250(5)',
                                   'output_key':'crossroads_entry_measurement',
                                   'method':'measure_entry','value_type':'object',
                                   'kind':'measured',
                                   'inputs':['actor-history.json','road-context.json',
                                             'video_frames.jsonl','trace.jsonl',
                                             'capture/evidence.jsonl']}],
                  'negative':{'remove':['actor-history.json'],
                              'error_contains':'Missing required source: actor-history.json'},
                  'status':'selected_cpu_prepared_original_unverified'}
        contract_path=HERE/suffix/'measurement-contract.json'
        put(contract_path,contract)
        primary=HERE/suffix/'primary/construction.json'
        fallback=HERE/suffix/'fallback2/construction.json'
        entries.append({'case_id':case_id,'kind':'delivery',
                        'construction':str(primary.relative_to(BASE)),
                        'construction_sha256':sha(primary),
                        'fixture_recipe':str((HERE/suffix/'fixture-recipe.json').relative_to(REPO)),
                        'measurement_contract':str(contract_path.relative_to(BASE)),
                        'measurement_procedure':{'entrypoint':'finalize.py'},
                        'candidate_risk':{'status':'physical',
                                          'reason':'Original four-view participant coverage may be incomplete'},
                        'candidates':[{'id':'fallback2',
                                       'construction':str(fallback.relative_to(BASE)),
                                       'construction_sha256':sha(fallback),
                                       'trigger':{'source':'original four-view pixels',
                                                  'metric':'all_participants_visible',
                                                  'failure_condition':'false or unreviewed'},
                                       'changed_knobs':['camera_policy']}],
                        'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                          'host_env_var':'CARLA_HOST',
                                          'port_env_var':'CARLA_PORT'}})
    runtime=json.loads((REPO/'batch.json').read_text())['runtime']['source_manifest_sha256']
    manifest={'format':'worker-execution-manifest','assignment_id':BASE.name,
              'runtime_manifest_sha256':runtime,'status':'branch_cpu_in_progress',
              'cases':entries}
    path=BASE/'branch-v1-manifest.json'
    put(path,manifest)
    print(json.dumps({'manifest_sha256':sha(path),'cases':len(entries)}))


if __name__=='__main__':
    build()
