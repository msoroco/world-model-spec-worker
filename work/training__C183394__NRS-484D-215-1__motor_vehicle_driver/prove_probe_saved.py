"""Exercise saved-only processing on diagnostic probe acquisitions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
MANIFEST = ROOT/'execution-manifest.json'
PROBES = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for probe in PROBES:
    case = AID+'__'+probe
    source = REPO/'.runtime-work/c183394'/('compat-'+probe+'-primary')
    attempt = REPO/'.runtime-work/c183394'/('saved-attempt-'+probe)
    output = REPO/'.runtime-work/c183394'/('saved-'+probe)
    if attempt.exists():
        shutil.rmtree(attempt)
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, attempt)
    selection_path = attempt/'candidate-selection.json'
    selection = json.loads(selection_path.read_text())
    selection['manifest_sha256'] = sha(MANIFEST)
    selection_path.write_text(json.dumps(selection, indent=2)+'\n')
    command = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', str(REPO/'runtime/library'),
               '--validator', str(REPO/'.runtime-work/c183394/decoder/.lake/build/bin/adapterCheck')]
    result = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
    folder = ROOT/'saved-proof'/probe
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'command.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'{probe}: {(result.stdout+result.stderr)[-1500:]}')
    receipt = output/'v0001/processing.json'
    shutil.copyfile(receipt, folder/'processing.json')
    if not json.loads(receipt.read_text()).get('passed'):
        raise ValueError('Saved-only receipt did not pass')
    entry = next(e for e in manifest['cases'] if e['case_id'] == case)
    entry['post_capture'].update(test_exit_code=0,
        test_log=str((folder/'processing.json').relative_to(ROOT)),
        test_log_sha256=sha(folder/'processing.json'))
    print('PASS', probe, flush=True)
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
