"""Run current safety-pair primary/fallback offline and compatibility proofs."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'execution-manifest.json'
DECODER = ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    with log.open('w') as stream:
        subprocess.run(args, cwd=ROOT, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove(entry, candidate):
    case_id = entry['case_id']
    suffix = case_id.rsplit('__', 1)[-1]
    ident = candidate['id']
    stamp = str(time_ns())
    offline = ROOT/'.runtime-work'/('c230671-'+suffix+'-'+ident+'-'+stamp+'-offline')
    compat = ROOT/'.runtime-work'/('c230671-'+suffix+'-'+ident+'-'+stamp+'-compat')
    base = [sys.executable, 'runtime.py']
    common = ['--manifest', str(MANIFEST), '--case', case_id]
    alternate = [] if ident == 'primary' else ['--candidate', ident]
    offline_command = base+['offline']+common+alternate+[
        '--output', str(offline), '--python', sys.executable]
    offline_log = HERE/(suffix+'-'+ident+'-offline.log')
    command(offline_command, offline_log)
    tested = HERE/(suffix+'-'+ident+'-offline-tests.log')
    shutil.copy2(offline/'offline.log', tested)
    compat_command = base+['compatibility']+common+alternate+[
        '--output', str(compat), '--library', 'runtime/library',
        '--validator', str(DECODER)]
    compat_log = HERE/(suffix+'-'+ident+'-compatibility.log')
    command(compat_command, compat_log)
    receipt_name = suffix+'-'+ident+'-compatibility.json'
    analysis_name = suffix+'-'+ident+'-compat-analysis.log'
    negative_name = suffix+'-'+ident+'-negative.log'
    for source, name in ((compat/'compatibility.json', receipt_name),
                         (compat/'compatibility-analysis.log', analysis_name),
                         (compat/'negative-analysis.log', negative_name)):
        shutil.copy2(source, HERE/name)
    receipt = json.loads((HERE/receipt_name).read_text())
    if (receipt.get('passed') is not True or
            receipt.get('case_id') != case_id or
            receipt.get('candidate_id') != ident or
            receipt.get('construction_sha256') != candidate['construction_sha256']):
        raise ValueError('Exact C230671 compatibility proof differs')
    candidate['offline'] = {
        'command': ' '.join(map(str, offline_command)), 'exit_code': 0,
        'log': tested.name, 'log_sha256': digest(tested),
        'construction_sha256': candidate['construction_sha256']}
    candidate['compatibility'] = {
        'receipt': receipt_name, 'sha256': digest(HERE/receipt_name),
        'log': analysis_name, 'negative_log': negative_name}
    return compat


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        if args.case_suffix and not entry['case_id'].endswith('__'+args.case_suffix):
            continue
        primary = {'id': 'primary',
                   'construction_sha256': entry['construction_sha256']}
        prove(entry, primary)
        entry['offline'] = primary['offline']
        entry['compatibility'] = primary['compatibility']
        entry['negative'] = {'log': primary['compatibility']['negative_log']}
        for candidate in entry['candidates']:
            prove(entry, candidate)
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
