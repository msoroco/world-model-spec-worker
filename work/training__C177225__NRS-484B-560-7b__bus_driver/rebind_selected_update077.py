"""Return current JSON-graph compatibility and saved receipts for eight candidates."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
INDEX = HERE / 'update075c-selected-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


index = json.loads(INDEX.read_text())
manifest = json.loads(MANIFEST.read_text())
if len(index['proofs']) != 8 or index['manifest_sha256'] != sha(MANIFEST):
    raise ValueError('Incomplete/stale selected chain index')
for proof in index['proofs']:
    case, candidate = proof['case'], proof['candidate']
    entry = next(x for x in manifest['cases'] if x['case_id'] == HERE.name + '__' + case)
    target = entry if candidate == 'primary' else next(x for x in entry['candidates']
                                                       if x['id'] == candidate)
    if 'output_dir' in proof:
        base = ROOT / proof['output_dir']
    else:
        base = ROOT / '.runtime-work/c177225-update071' / case / candidate
    compat_source = base / 'compatibility/compatibility.json'
    saved_source = base / 'saved/v0001/processing.json'
    compat = json.loads(compat_source.read_text())
    saved = json.loads(saved_source.read_text())
    if (compat['case_id'] != entry['case_id'] or compat['candidate_id'] != candidate or
            compat['construction_sha256'] != target['construction_sha256'] or
            saved['case_id'] != entry['case_id'] or saved['candidate_id'] != candidate or
            saved['passed'] is not True or saved['missing_evidence'] is not False):
        raise ValueError('Selected result differs: ' + case + '/' + candidate)
    prefix = f'update077-{case}-{candidate}'
    copies = {
        'receipt': (compat_source, HERE / f'{prefix}-compatibility-receipt.json'),
        'analysis': (base / 'compatibility/compatibility-analysis.log',
                     HERE / f'{prefix}-compatibility-analysis.log'),
        'negative': (base / 'compatibility/negative-analysis.log',
                     HERE / f'{prefix}-negative-analysis.log'),
        'saved': (saved_source, HERE / f'{prefix}-saved-receipt.json'),
    }
    for source, destination in copies.values():
        shutil.copyfile(source, destination)
    if (sha(copies['analysis'][1]) != compat['log_sha256'] or
            sha(copies['negative'][1]) != compat['negative_log_sha256']):
        raise ValueError('Compatibility logs differ from receipt')
    target['offline'] = {
        'command': (f'.venv-cpu/bin/python runtime.py offline --manifest '
                    f'{(HERE / ("update071-" + case + "-fallback1-manifest.json") if candidate == "fallback1" else MANIFEST).relative_to(ROOT)} '
                    f'--case {entry["case_id"]} --candidate {candidate} '
                    f'--output {base.relative_to(ROOT)}/offline'),
        'construction_sha256': target['construction_sha256'],
        'exit_code': 0,
        'log': Path(proof['offline']['log']).name,
        'log_sha256': proof['offline']['sha256'],
        'simulation_started': False,
    }
    target['compatibility'] = {
        'receipt': copies['receipt'][1].name,
        'sha256': sha(copies['receipt'][1]),
        'log': copies['analysis'][1].name,
        'negative_log': copies['negative'][1].name,
    }
    target['saved_processing'] = {
        'receipt': copies['saved'][1].name,
        'sha256': sha(copies['saved'][1]),
        'log': Path(proof['saved']['log']).name,
        'scope': 'Current JSON-graph synthetic diagnostic; no original Native acceptance',
    }
    if candidate == 'primary':
        entry['negative'] = {'log': copies['negative'][1].name}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'candidate_chains': len(index['proofs']),
                  'manifest_sha256': sha(MANIFEST)}))
