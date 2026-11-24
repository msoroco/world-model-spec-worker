"""Bind both exact selected CPU primaries and fallbacks without claiming physical delivery."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'draft-execution-manifest.json'
DEST=HERE/'selected-cpu-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old=json.loads(SOURCE.read_text())
    if old.get('assignment_id')!=HERE.name or len(old.get('cases',[]))!=2:
        raise ValueError('Exact two-case draft manifest required')
    selected=[]
    for case in old['cases']:
        if case.get('id')!='primary' or len(case.get('candidates',[]))!=3:
            raise ValueError('Primary and three fallbacks required per case')
        for candidate in [case]+case['candidates']:
            path=HERE/candidate['construction']
            if sha(path)!=candidate['construction_sha256']:
                raise ValueError('Source construction digest differs: '+str(path))
            body=json.loads(path.read_text())
            if body.get('case_id')!=case['case_id']:
                raise ValueError('Construction case identity differs')
        current=dict(case)
        current['kind']='selected_cpu_draft_not_delivery_ready'
        current['delivery_readiness']='incomplete_original_native_and_strict_v2'
        selected.append(current)
    out={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':HERE.name,
         'runtime_manifest_sha256':old['runtime_manifest_sha256'],
         'source_draft_manifest_sha256':sha(SOURCE),'status':'partial','cases':selected}
    DEST.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'selected_case_count':2,'candidate_count':8,'manifest_sha256':sha(DEST)},sort_keys=True))


if __name__=='__main__':main()
