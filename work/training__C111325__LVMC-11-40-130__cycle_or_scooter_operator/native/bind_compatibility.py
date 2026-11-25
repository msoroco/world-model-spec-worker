"""Bind selected exact-case compatibility positive/negative receipts and logs."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(choice, condition, candidate):
    source = REPO/'.runtime-work'/f'c111325-final-compat-{condition}-{candidate}'
    receipt = json.loads((source/'compatibility.json').read_text())
    if not receipt['passed'] or receipt['candidate_id'] != candidate or receipt['construction_sha256'] != choice['construction_sha256']:
        raise ValueError('Stale selected compatibility: '+condition+' '+candidate)
    folder = FOLDER/'proofs'/condition/candidate
    folder.mkdir(parents=True, exist_ok=True)
    for name, target in [('compatibility.json','compatibility.json'),
                         ('compatibility-analysis.log','analysis.log'),
                         ('negative-analysis.log','negative-analysis.log')]:
        shutil.copyfile(source/name,folder/target)
        if (folder/target).stat().st_size > 2*1024*1024:
            raise ValueError('Proof file over size cap')
    choice['compatibility'] = {'receipt': str((folder/'compatibility.json').relative_to(FOLDER)),
                               'sha256': sha(folder/'compatibility.json'),
                               'log': str((folder/'analysis.log').relative_to(FOLDER)),
                               'negative_log': str((folder/'negative-analysis.log').relative_to(FOLDER))}
    return choice['compatibility']


def main():
    path = FOLDER/'execution-manifest.json'
    manifest = json.loads(path.read_text())
    count = 0
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__',1)[-1]
        bind(entry,condition,'primary'); count += 1
        bind(entry['candidates'][0],condition,'fallback1'); count += 1
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'compatibility_bound': count, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
