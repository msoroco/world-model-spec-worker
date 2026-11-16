"""Bind already-run selected CPU diagnostics to the executable manifest.

The source attempts are synthetic diagnostics. This script does not turn them
into Native observations or acceptance evidence.
"""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def source(case, candidate, kind):
    if case == 'witness_1' and candidate == 'primary':
        stem = f'c111256-selected-{kind}-witness1'
    else:
        stem = f'c111256-selected-{case}-{candidate}-{kind}'
    return ROOT / '.runtime-work' / stem


def keep(source_path, dest_path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, dest_path)
    return str(dest_path.relative_to(HERE)), sha(dest_path)


manifest = json.loads(MANIFEST.read_text())
old_sha = sha(MANIFEST)
for entry in manifest['cases']:
    case = entry['case_id'].rsplit('__', 1)[1]
    for candidate in ['primary', *entry['candidates']]:
        ident = 'primary' if candidate == 'primary' else candidate['id']
        selected = entry if ident == 'primary' else candidate
        target = HERE / 'selected-proofs' / case / ident
        offline = source(case, ident, 'offline')
        compatibility = source(case, ident, 'compat')
        offline_log, offline_sha = keep(offline / 'offline.log', target / 'offline.log')
        receipt, receipt_sha = keep(compatibility / 'compatibility.json', target / 'compatibility.json')
        positive, _ = keep(compatibility / 'compatibility-analysis.log', target / 'analysis.log')
        negative, _ = keep(compatibility / 'negative-analysis.log', target / 'negative.log')
        selected['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest {MANIFEST} --case {entry["case_id"]} --candidate {ident} --output {offline} --python .venv-cpu/bin/python',
            'exit_code': 0,
            'construction_sha256': selected['construction_sha256'],
            'log': offline_log,
            'log_sha256': offline_sha,
        }
        selected['compatibility'] = {
            'receipt': receipt,
            'sha256': receipt_sha,
            'log': positive,
            'negative_log': negative,
        }
        if ident == 'primary':
            entry['negative'] = {'log': negative}
    construction = json.loads((HERE / entry['construction']).read_text())
    paths = {item['path'] for item in construction['files']}
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    atoms = set(config.get('required_atoms', [])) | {item['name'] for item in construction['recording_description']['channels']}
    entry['acquisition'] = {
        atom: {
            'entrypoint': 'finalize.py' if atom.startswith(('dev.', 'drv.', 'ru.')) else 'runner.py',
            'method': 'Original Native sampled channel and saved source join, with exact case map and actor readback required',
            'evidence': 'Synthetic CPU fixture is diagnostic; original Native source and independent pixel review remain required',
        } for atom in sorted(atoms)
    }
    assert all(spec['entrypoint'] in paths for spec in entry['acquisition'].values())
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
write(MANIFEST, manifest)
write(HERE / 'selected-receipt-binding.json', {
    'format': 'c111256-selected-receipt-binding',
    'staged_manifest_sha256': old_sha,
    'enriched_manifest_sha256': sha(MANIFEST),
    'selected_constructions': 16,
    'scope': 'Exact synthetic CPU offline and compatibility receipts; physical Native and delivery acceptance unproven',
})
print(json.dumps(json.loads((HERE / 'selected-receipt-binding.json').read_text()), indent=2))
