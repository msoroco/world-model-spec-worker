"""Refresh source-bound construction after local implementation edits."""
import hashlib, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
IDS=json.loads((REPO/'partitions/demo-test-03.json').read_text())['assignment_ids']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
for aid in IDS:
    root=REPO/'work'/aid
    for name in ('runner.py','analyze.py'):
        if root/name!=HERE/name:shutil.copyfile(HERE/name,root/name)
    shutil.copyfile(HERE/'test_template.py',root/'tests/test_case.py')
    construction=json.loads((root/'construction.json').read_text())
    for file in construction['files']:
        file['content']=(root/file['path']).read_text()
    write(root/'construction.json',construction)
    manifest=json.loads((root/'execution-manifest.json').read_text())
    manifest['cases'][0]['construction_sha256']=sha(root/'construction.json')
    write(root/'execution-manifest.json',manifest)
