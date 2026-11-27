"""Bind selected recorded-only fixture processing receipts."""
import hashlib
import json
import shutil
from pathlib import Path

root=Path(__file__).resolve().parents[1]
repo=root.parents[1]
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    version='v10' if suffix=='conflict_25' else 'v9'
    saved_root=repo/'.runtime-work/c229987'/('saved-'+version+'-'+suffix)
    sources=sorted(saved_root.glob('v*/processing.json'))
    assert sources,(suffix,'missing saved-only proof')
    source=sources[-1]
    receipt=json.loads(source.read_text())
    assert receipt['passed'] and receipt['recorded_only'] and receipt['case_id']==case
    assert receipt['analysis_revision']['construction_sha256']==entry['construction_sha256']
    folder=root/'saved';folder.mkdir(exist_ok=True)
    proof=folder/(suffix+'-processing.json');log=folder/(suffix+'-processing.log')
    shutil.copyfile(source,proof)
    shutil.copyfile(repo/'.runtime-work/c229987'/('saved-'+version+'-'+suffix+'.stdout'),log)
    command=(f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{root.name}/execution-manifest.json '
             f'--case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT '
             f'--library runtime/library --validator $DECODER')
    entry['post_capture']={'command':command,'feedback_command':command,
                           'recorded_only':True,'test_exit_code':0,
                           'test_log':str(log.relative_to(root)),'test_log_sha256':sha(log),
                           'processing_receipt':str(proof.relative_to(root)),
                           'processing_receipt_sha256':sha(proof)}
manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
