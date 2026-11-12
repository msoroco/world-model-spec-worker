"""Assemble the four proved selected cases into a partial delivery inventory.

This keeps missing independent physical and acceptance proofs explicit; it
does not declare the assignment ready.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PREFIXES=('primary','right','separated','opposite')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries=[]
    for prefix in PREFIXES:
        source=json.loads((HERE/(prefix+'-candidate-manifest.json')).read_text())
        entry=copy.deepcopy(source['cases'][0])
        saved={'primary':'primary-saved-v3.log',
               'right':'right-saved-v2.log',
               'separated':'separated-saved-v1.log',
               'opposite':'opposite-saved-v1.log'}[prefix]
        entry['post_capture']={
            'recorded_only':True,
            'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck',
            'feedback_command':'cat $OUTPUT/feedback.json',
            'test_log':saved,'test_log_sha256':sha(HERE/saved),
            'test_exit_code':0,
            'proof_scope':'isolated-manifest diagnostic saved processing; canonical-manifest rerun pending'}
        entries.append(entry)
    manifest={'format':'worker-execution-manifest',
              'assignment_id':HERE.name,
              'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
              'status':'partial_delivery_draft',
              'cases':entries,
              'outstanding':['canonical-manifest saved-processing reruns',
                             'physical-preparation fixtures',
                             'independent delivery acceptance proofs',
                             'validated semantic stage proposals']}
    path=HERE/'execution-manifest.json'
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'path':str(path.relative_to(REPO)),
            'case_ids':[row['case_id'] for row in entries],
            'status':manifest['status']}


if __name__=='__main__':
    print(json.dumps(build(),indent=2))
