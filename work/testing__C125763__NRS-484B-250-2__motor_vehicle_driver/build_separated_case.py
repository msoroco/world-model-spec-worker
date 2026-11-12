"""Build the selected left-side separated-entry timing comparison.

The retained crossing/sign/approaches are identical to the primary synthetic
CPU case. Earlier other release and original-body entry produce a larger
measured gap, without assigning a legal threshold to approximate timing.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIX='yield_ego_left_separated'
CASE=HERE.name+'__'+SUFFIX
PRIMARY=HERE.name+'__yield_ego_left_near_time'
OUT=HERE/'cases'/SUFFIX


def serialized(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def embedded(files,path):
    return next(row for row in files if row['path']==path)


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    construction=copy.deepcopy(json.loads(
        (HERE/'cases/yield_ego_left_near_time/construction.json').read_text()))
    construction['case_id']=CASE
    files=construction['files']
    config_row=embedded(files,'config.json')
    config=json.loads(config_row['content'])
    config['selected_case_id']=CASE
    config['other_release_frame']=5
    config_row['content']=serialized(config)
    test=embedded(files,'tests/test_bundle.py')
    test['content']=test['content'].replace('yield_ego_left_near_time',SUFFIX)
    (OUT/'construction.json').write_text(serialized(construction))

    diagnostic=copy.deepcopy(json.loads((HERE/'diagnostic.json').read_text()))
    history=[json.loads(line) for line in diagnostic['files']['crossing_history.jsonl'].splitlines()]
    entered_other=history[30]['other']
    for row in history[20:30]:
        row['other']=copy.deepcopy(entered_other)
    diagnostic['files']['crossing_history.jsonl']=''.join(
        json.dumps(row,allow_nan=False)+'\n' for row in history)
    capture_manifest=json.loads(diagnostic['files']['capture/manifest.json'])
    capture_manifest['case_id']=CASE
    diagnostic['files']['capture/manifest.json']=serialized(capture_manifest)
    source=OUT/'diagnostic.json';source.write_text(serialized(diagnostic))
    source_rel=str(source.relative_to(REPO));checksum=sha(source)
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':source_rel,'sha256':checksum}],
            'generator':{'source':source_rel,'sha256':checksum}}
    (OUT/'diagnostic-recipe.json').write_text(serialized(recipe))

    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
              'status':'isolated_partial_separated_diagnostic',
              'cases':[{'case_id':CASE,'kind':'delivery',
                        'construction':str((OUT/'construction.json').relative_to(HERE)),
                        'construction_sha256':sha(OUT/'construction.json'),
                        'measurement_procedure':{'entrypoint':'finalizer.py'},
                        'measurement_contract':'measurement-contract.json',
                        'fixture_recipe':str((OUT/'diagnostic-recipe.json').relative_to(REPO)),
                        'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                          'host_env_var':'CARLA_HOST',
                                          'port_env_var':'CARLA_PORT'}}]}
    (HERE/'separated-candidate-manifest.json').write_text(serialized(manifest))

    plan_path=HERE/'case-plan.json';plan=json.loads(plan_path.read_text())
    for row in plan['requirement_dispositions']:
        if row['status']=='selected_required' and PRIMARY in row.get('case_ids',[]):
            row['case_ids']=list(dict.fromkeys(row['case_ids']+[CASE]))
    plan_path.write_text(serialized(plan))
    proposals_path=HERE/'proposals/cases.json'
    proposals=json.loads(proposals_path.read_text())
    proposal=copy.deepcopy(next(c for c in proposals['cases'] if c['case_id']==PRIMARY))
    proposal['case_id']=CASE
    proposal['rationale']='Same synthetic left-side approach and sign; earlier other release produces a measured separated entry gap; physical site unverified'
    proposal['variable_assignments']['other_release_frame']['value']=5
    proposal['probe']['target_value_or_branch']=SUFFIX
    proposal['deliberate_differences']=['Earlier other release frame and measured complete-body entry-time gap; no legal cutoff assigned']
    proposals['cases']=[c for c in proposals['cases'] if c['case_id']!=CASE]+[proposal]
    proposals_path.write_text(serialized(proposals))
    return manifest


if __name__=='__main__':
    print(serialized(build()),end='')
