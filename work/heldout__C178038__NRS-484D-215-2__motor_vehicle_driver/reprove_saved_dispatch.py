"""Rerun saved-only primary proofs after Native runner revision."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
manifest = json.loads(MANIFEST.read_text())

for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case.split('__')[-1]
    token = uuid4().hex[:8]
    prefix = ROOT / '.runtime-work' / f'c178038-{suffix}-dispatch-saved-{token}'
    fixture = Path(str(prefix) + '-fixture')
    attempt = Path(str(prefix) + '-attempt')
    output = Path(str(prefix) + '-output')
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                    '--recipe', str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'offline',
                    '--manifest', str(MANIFEST), '--case', case,
                    '--output', str(attempt), '--python', sys.executable],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    for path in fixture.rglob('*'):
        if path.is_file():
            target = attempt / path.relative_to(fixture)
            if target.exists():
                raise ValueError('Diagnostic source shadows construction: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    directory = HERE / ('sweep-probes' if suffix.startswith('illumination_gap_sweep-') else
                        'context-probes' if suffix.startswith(('day_', 'shoulder_')) else 'night-probes')
    log = directory / f'{suffix}-saved-command.log'
    with log.open('w') as stream:
        subprocess.run(command, cwd=ROOT, check=True, stdout=stream, stderr=subprocess.STDOUT)
    source = output / 'v0001/processing.json'
    proof = json.loads(source.read_text())
    if (not proof['passed'] or not proof['originals_preserved'] or
            not proof['timestamp_joins']['passed'] or
            not proof['final_video_checks']['passed'] or proof['missing_evidence'] or
            proof['native_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Saved-only proof incomplete or stale: ' + suffix)
    retained = directory / f'{suffix}-saved-processing.json'
    shutil.copyfile(source, retained)
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR',
        'feedback_command': 'cat $OUTPUT/v0001/feedback.json',
        'test_log': str(log.relative_to(HERE)),
        'test_log_sha256': sha256(log.read_bytes()).hexdigest(),
        'test_exit_code': 0}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(suffix, sha256(retained.read_bytes()).hexdigest(), flush=True)
