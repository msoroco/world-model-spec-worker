"""Run pinned saved-only processing on each primary diagnostic source bundle."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT/'execution-manifest.json'
VALIDATOR = REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name+'__')
        source = REPO/'.runtime-work'/('c101303-compat4-'+suffix+'-primary')
        attempt = REPO/'.runtime-work'/('c101303-saved-'+suffix+'-attempt')
        if attempt.exists():
            shutil.rmtree(attempt)
        materialize = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'),
                       'materialize', '--manifest', str(MANIFEST), '--case',
                       entry['case_id'], '--output', str(attempt)]
        result = subprocess.run(materialize, cwd=REPO, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(result.stdout[-1200:])
        receipt = json.loads((ROOT/entry['compatibility']['receipt']).read_text())
        for name in receipt['fixture_manifest']:
            original = source/name
            if not original.is_file():
                raise RuntimeError('diagnostic source missing: '+name)
            target = attempt/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original,target)
        output = REPO/'.runtime-work'/('c101303-saved-'+suffix)
        if output.exists():
            shutil.rmtree(output)
        command = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST), '--case',
                   entry['case_id'], '--attempt', str(attempt), '--output',
                   str(output), '--library', str(REPO/'runtime/library'),
                   '--validator', str(VALIDATOR)]
        result = subprocess.run(command, cwd=REPO, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = ROOT/('saved-'+suffix+'.log')
        log.write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(suffix+': '+result.stdout[-1200:])
        entry['post_capture'] = {'recorded_only': True,
            'command': ' '.join(command), 'feedback_command': ' '.join(command),
            'test_log': log.name, 'test_log_sha256': sha(log), 'test_exit_code': 0}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print(f"Saved-only processing passed for all {len(manifest['cases'])} primary diagnostic cases.")


if __name__ == '__main__':
    main()
