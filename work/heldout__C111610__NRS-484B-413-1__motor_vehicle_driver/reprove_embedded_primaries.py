"""Rebind older exact bundles to their embedded versions and rerun CPU proofs."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'execution-manifest.json'
TARGETS = {'pedestrian_horn_before_turn', 'pedestrian_farther_horn_before_turn',
           'pedestrian_horn_after_onset'}
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with (ROOT / log).open('w') as output:
        subprocess.run(command, cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)


def save(value):
    MANIFEST.write_text(json.dumps(value, indent=2) + '\n')


def rebind(entry):
    path = ROOT / entry['construction']
    value = json.loads(path.read_text())
    changed = []
    for item in value['files']:
        if item.get('source') and (REPO / item['source']).read_text() != item['content']:
            changed.append(item['path'])
            item.pop('source')
    if changed:
        path.write_text(json.dumps(value, indent=2) + '\n')
        entry['construction_sha256'] = digest(path)
    return changed


def prove(manifest, entry):
    case = entry['case_id']
    token = uuid4().hex[:10]
    relative = str(MANIFEST.relative_to(REPO))
    offline = [PY, 'runtime.py', 'offline', '--manifest', relative, '--case', case,
               '--output', f'.runtime-work/c111610-rebound-offline-{token}', '--python', PY]
    log = entry['offline']['log']
    run(offline, log)
    entry['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                        'log': log, 'log_sha256': digest(ROOT / log),
                        'construction_sha256': entry['construction_sha256']}
    save(manifest)

    output = REPO / f'.runtime-work/c111610-rebound-compat-{token}'
    command = [PY, 'runtime.py', 'compatibility', '--manifest', relative, '--case', case,
               '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    with (REPO / f'.runtime-work/c111610-rebound-compat-{token}.log').open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)
    spec = entry['compatibility']
    shutil.copy2(output / 'compatibility.json', ROOT / spec['receipt'])
    shutil.copy2(output / 'negative-analysis.log', ROOT / spec['negative_log'])
    proof = json.loads((ROOT / spec['receipt']).read_text())
    if not proof['passed'] or proof['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Rebound primary compatibility failed: ' + case)
    if digest(ROOT / spec['log']) != proof['log_sha256']:
        shutil.copy2(output / 'compatibility-analysis.log', ROOT / spec['log'])
    spec['sha256'] = digest(ROOT / spec['receipt'])
    save(manifest)

    attempt = REPO / f'.runtime-work/c111610-rebound-attempt-{token}'
    materialize(MANIFEST, case, attempt)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111610-rebound-source-') as temp:
        fixture = Path(temp) / 'fixture'
        materialize_fixture(REPO, REPO / entry['fixture_recipe'], fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError('Fixture source shadows construction: ' + source.name)
            shutil.copytree(source, target) if source.is_dir() else shutil.copy2(source, target)
    processed = REPO / f'.runtime-work/c111610-rebound-saved-{token}'
    command = [PY, 'runtime.py', 'process-saved', '--manifest', relative, '--case', case,
               '--attempt', str(attempt.relative_to(REPO)), '--output', str(processed.relative_to(REPO)),
               '--library', 'runtime/library', '--validator',
               '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    spec = entry['saved_processing']
    run(command, spec['log'])
    shutil.copy2(processed / 'v0001/processing.json', ROOT / spec['receipt'])
    result = json.loads((ROOT / spec['receipt']).read_text())
    if not (result['passed'] and result['originals_preserved'] and not result['missing_evidence']):
        raise ValueError('Rebound primary saved processing failed: ' + case)
    spec.update(command=' '.join(command), exit_code=0, log_sha256=digest(ROOT / spec['log']),
                receipt_sha256=digest(ROOT / spec['receipt']))
    entry['post_capture']['test_log_sha256'] = spec['log_sha256']
    save(manifest)
    return attempt, processed


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        if short not in TARGETS:
            continue
        mismatches = rebind(entry)
        if not mismatches:
            print(short, 'already source-matched', flush=True)
            continue
        save(manifest)
        attempt, processed = prove(manifest, entry)
        print(short, 'rebound', mismatches, 'construction', entry['construction_sha256'],
              'saved', processed.relative_to(REPO), flush=True)
    return manifest


if __name__ == '__main__':
    main()
