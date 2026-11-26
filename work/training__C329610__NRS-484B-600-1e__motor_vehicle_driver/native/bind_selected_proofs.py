"""Copy stable compact CPU proof receipts into selected manifest entries."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text()
    target.write_text('\n'.join(line.rstrip() for line in content.splitlines()).rstrip() + ('\n' if content else ''))


def bind():
    draft = ROOT/'selected-draft-execution-manifest.json'
    obj = json.loads(draft.read_text())
    for entry in obj['cases']:
        suffix = entry['case_id'].removeprefix(AID+'__')
        for candidate in [entry, *entry['candidates']]:
            name = candidate.get('id', 'primary')
            stem = suffix+'-'+name
            offline_dir = Path('.runtime-work')/('c329610-selected-offline-'+stem+'-v2')
            compatibility_dir = Path('.runtime-work')/('c329610-selected-compat-'+stem+'-v2')
            proof = ROOT/'selected-proofs'/stem
            if not (compatibility_dir/'compatibility.json').exists():
                raise ValueError('Compatibility proof still pending: '+stem)
            for src, dst in (('offline.log','offline.log'),):
                clean_copy(offline_dir/src, proof/dst)
            for src in ('compatibility.json','compatibility-analysis.log','negative-analysis.log'):
                clean_copy(compatibility_dir/src, proof/src)
            command = ('.venv-cpu/bin/python runtime.py offline --manifest work/'+AID+
                '/selected-draft-execution-manifest.json --case '+entry['case_id']+
                ' --candidate '+name+' --output .runtime-work/c329610-selected-offline-'+stem+
                '-v2 --python $PWD/.venv-cpu/bin/python')
            candidate['offline'] = {
                'command': command, 'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0, 'log': str((proof/'offline.log').relative_to(ROOT)),
                'log_sha256': sha(proof/'offline.log')}
            candidate['compatibility'] = {
                'receipt': str((proof/'compatibility.json').relative_to(ROOT)),
                'sha256': sha(proof/'compatibility.json'),
                'log': str((proof/'compatibility-analysis.log').relative_to(ROOT)),
                'negative_log': str((proof/'negative-analysis.log').relative_to(ROOT))}
            if name == 'primary':
                entry['negative'] = {'log': candidate['compatibility']['negative_log']}
    obj['status'] = 'selected_cpu_proofs_in_progress'
    (ROOT/'execution-manifest.json').write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    bind()
