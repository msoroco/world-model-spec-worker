"""Run and bind public positive/missing-source compatibility for probe candidates."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
PROBES = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')
MANIFEST = ROOT/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for probe in PROBES:
    entry = next(e for e in manifest['cases'] if e['case_id'] == AID+'__'+probe)
    for candidate in ('primary', 'fallback1'):
        output = REPO/'.runtime-work'/'c183394'/('compat-'+probe+'-'+candidate)
        bound = ROOT/'compatibility'/f'{probe}-{candidate}'
        bound.mkdir(parents=True, exist_ok=True)
        command = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'),
                   'compatibility', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--candidate', candidate, '--output', str(output),
                   '--library', str(REPO/'runtime/library'), '--validator',
                   str(REPO/'.runtime-work/c183394/decoder/.lake/build/bin/adapterCheck')]
        if not (output/'compatibility.json').is_file():
            if output.exists():
                shutil.rmtree(output)
            result = subprocess.run(command, cwd=REPO, env=os.environ,
                                    capture_output=True, text=True)
            (bound/'command.log').write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{probe} {candidate}: {(result.stdout+result.stderr)[-1500:]}')
        else:
            (bound/'command.log').write_text('Reused complete public compatibility output from same manifest and exact construction.\n')
        for source, target in [('compatibility.json', 'compatibility.json'),
                               ('compatibility-analysis.log', 'analysis.log'),
                               ('negative-analysis.log', 'negative.log')]:
            shutil.copyfile(output/source, bound/target)
        receipt = json.loads((bound/'compatibility.json').read_text())
        construction = entry if candidate == 'primary' else entry['candidates'][0]
        if receipt['construction_sha256'] != construction['construction_sha256'] or receipt['case_id'] != entry['case_id']:
            raise ValueError('Public compatibility receipt changed identity')
        construction['compatibility'] = {'receipt': str((bound/'compatibility.json').relative_to(ROOT)),
            'sha256': sha(bound/'compatibility.json'),
            'log': str((bound/'analysis.log').relative_to(ROOT)),
            'negative_log': str((bound/'negative.log').relative_to(ROOT))}
        print('PASS', probe, candidate, flush=True)
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
