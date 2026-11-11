"""Run saved-only synthetic proof for the three nighttime comparison cases."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'night-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'


def run():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases'][1:]:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[1]
        prefix = ROOT / '.runtime-work' / f'c178038-{suffix}-saved-20261111a'
        fixture = Path(str(prefix) + '-fixture')
        attempt = Path(str(prefix) + '-attempt')
        output = Path(str(prefix) + '-output')
        subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                        '--recipe', str(ROOT / entry['fixture_recipe']),
                        '--output', str(fixture)], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'offline',
                        '--manifest', str(MANIFEST), '--case', case_id,
                        '--output', str(attempt), '--python', sys.executable],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        for path in fixture.rglob('*'):
            if path.is_file():
                target = attempt / path.relative_to(fixture)
                if target.exists():
                    raise ValueError('Diagnostic source shadows materialization: ' + str(target))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', case_id,
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        log = HERE / 'night-probes' / f'{suffix}-saved-command.log'
        with log.open('w') as stream:
            subprocess.run(command, cwd=ROOT, check=True,
                           stdout=stream, stderr=subprocess.STDOUT)
        receipt = output / 'v0001/processing.json'
        proof = json.loads(receipt.read_text())
        if not (proof['passed'] and proof['originals_preserved'] and
                proof['timestamp_joins']['passed'] and
                proof['final_video_checks']['passed'] and
                not proof['missing_evidence']):
            raise ValueError('Saved-only proof incomplete: ' + suffix)
        saved = HERE / 'night-probes' / f'{suffix}-saved-processing.json'
        shutil.copyfile(receipt, saved)
        print(suffix, sha256(saved.read_bytes()).hexdigest())


if __name__ == '__main__':
    run()
