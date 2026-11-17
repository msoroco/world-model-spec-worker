"""Resolve optional, source-bound recovery of missing historical judgment metadata.

The original canonical case remains unchanged. Only absent judgment references
and absent axis-variable mappings may be recovered from its original cases job.
"""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(value,message):
    if not value:
        raise ValueError(message)

def resolve(root,member,original_case,read):
    root=Path(root).resolve()
    reference=member.get('judgment_metadata_recovery')
    if not reference:
        return original_case,{}
    need(isinstance(reference,dict) and set(reference)=={'path','sha256'},
         'Invalid judgment metadata reference')
    def path(relative):
        need(isinstance(relative,str) and not Path(relative).is_absolute(),
             'Recovery source must be relative')
        value=(root/relative).resolve()
        need(root in value.parents and value.is_file(),'Recovery source escapes root or is missing')
        return value
    receipt_path=path(reference['path'])
    need(sha(receipt_path)==reference['sha256'],'Judgment recovery receipt hash differs')
    proof=read(receipt_path)
    need(proof.get('format')=='source-bound-judgment-case-metadata-v1',
         'Unsupported judgment recovery receipt')
    need(proof['recording_id']==member['recording_id'] and
         proof['case_id']==member['case_id']==original_case['case_id'],
         'Recovered case identity differs')
    original=path(proof['original_case_path'])
    need(original==root/'recordings'/member['recording_id']/'evidence/case.json',
         'Recovery does not name original canonical case')
    need(sha(original)==proof['original_case_sha256'] and read(original)==original_case,
         'Original canonical case changed')
    artifact_path=path(proof['source_artifact_path'])
    need(sha(artifact_path)==proof['source_artifact_sha256'],'Original cases artifact hash differs')
    artifact=read(artifact_path)
    database=path(proof['source_database'])
    before=sha(database)
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT j.stage,j.artifact_id,a.payload FROM jobs j '
                       'JOIN artifacts a ON a.id=j.artifact_id WHERE j.id=?',
                       (proof['source_job_id'],)).fetchone()
    need(before==sha(database),'Historical source database changed during read')
    need(row and row[0]=='cases' and row[1]==proof['source_artifact_id'] and
         hashlib.sha256(row[2].encode()).hexdigest()==proof['source_artifact_sha256'] and
         json.loads(row[2])==artifact,'Recovery is not the original frozen cases artifact')
    matches=[c for c in artifact['cases'] if c['case_id']==proof['case_id']]
    need(len(matches)==1 and matches[0]==original_case,'Original frozen case differs')
    specs=[s for s in artifact['sweep_specs']
           if s['sweep_id']==proof['source_sweep_id']==original_case.get('sweep_id')]
    need(len(specs)==1,'Original frozen sweep ambiguous or missing')
    spec=specs[0]
    need(spec['spec_version']==proof['source_sweep_version']==
         original_case['sweep_spec_version'],'Original frozen sweep version differs')
    need(spec['target_law_id']==original_case['target_law_id']==member['law_id'],
         'Original sweep law differs')
    expected=copy.deepcopy(original_case)
    refs=expected.get('judgment_refs')
    if refs:
        need(refs==spec['judgment_refs'],'Cannot replace existing judgment identity')
    else:
        expected['judgment_refs']=copy.deepcopy(spec['judgment_refs'])
    for axis in expected['sweep_measurements']:
        candidates=[a for a in spec['axes']
                    if all(a[k]==axis[k] for k in ('observable','unit','measurement'))]
        need(len(candidates)==1,'Original axis identity or measurement differs')
        variable=candidates[0]['variable']
        need(variable in original_case['sweep_point'],'Original target mapping missing')
        need('variable' not in axis or axis['variable']==variable,
             'Cannot replace existing axis mapping')
        axis['variable']=variable
    recovered=path(proof['recovered_case_path'])
    need(sha(recovered)==proof['recovered_case_sha256'],'Recovered case hash differs')
    result=read(recovered)
    need(result==expected,'Recovery changes fields beyond missing source metadata')
    need(proof.get('original_case_unchanged') is True and
         proof.get('measured_values_changed') is False and
         proof.get('targets_changed') is False,'Recovery must preserve source values')
    return result,{str(database.relative_to(root)):before}
