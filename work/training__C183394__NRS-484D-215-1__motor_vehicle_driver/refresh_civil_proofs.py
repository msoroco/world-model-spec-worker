"""Rebind seven exact cases after adding original UTC tick capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
MANIFEST = ROOT / 'execution-manifest.json'
SUFFIXES = ('condition_a', 'condition_b', 'distance_below_500ft',
            'distance_at_500ft', 'distance_above_500ft',
            'visibility_dim', 'visibility_high')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load():
    return json.loads(MANIFEST.read_text())


def save(value):
    MANIFEST.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def find(manifest, suffix):
    return next(e for e in manifest['cases'] if e['case_id'] ==
                AID + ('__selected_6fb122bc__' if suffix.startswith('condition_') else '__') + suffix)


def short(suffix):
    return suffix[-1] if suffix.startswith('condition_') else suffix


def run(command, *, output=None):
    result = subprocess.run(command, cwd=REPO, env=os.environ,
                            capture_output=True, text=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(command) + '\n' +
                           (result.stdout + result.stderr)[-1500:])


def sync():
    manifest = load()
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        entry['construction_sha256'] = sha(ROOT / entry['construction'])
        for name in ('offline', 'compatibility', 'physical_preparation',
                     'post_capture', 'negative'):
            entry.pop(name, None)
        for candidate in entry['candidates']:
            candidate['construction_sha256'] = sha(ROOT / candidate['construction'])
            candidate.pop('offline', None)
            candidate.pop('compatibility', None)
    save(manifest)
    print('SYNC seven construction hashes', flush=True)


def offline():
    manifest = load()
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        for candidate in ('primary', 'fallback1'):
            output = REPO / '.runtime-work' / 'c183394' / ('civil-offline-' + suffix + '-' + candidate)
            if output.exists():
                shutil.rmtree(output)
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output),
                       '--python', str(REPO / '.venv-cpu/bin/python')]
            run(command)
            target = ROOT / 'offline' / (short(suffix) + '-' + candidate + '.log')
            shutil.copyfile(output / 'offline.log', target)
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            selected['offline'] = {'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': selected['construction_sha256'],
                'command': ' '.join(command), 'exit_code': 0,
                'log': str(target.relative_to(ROOT)), 'log_sha256': sha(target)}
            print('OFFLINE', suffix, candidate, flush=True)
    save(manifest)


def physical():
    manifest = load()
    lifecycle = json.loads((ROOT / 'native/physical-condition_a-receipt.json').read_text())['lifecycle']
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': [], 'lifecycle': lifecycle}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            command = [str(REPO / '.venv-cpu/bin/python'), '-B',
                       str(ROOT / 'native/prove_physical.py'), '--case', suffix,
                       '--kind', kind]
            log = ROOT / 'native' / f'physical-{suffix}-{kind}.log'
            run(command, output=log)
            result = ROOT / 'native' / f'physical-{suffix}-{kind}.json'
            receipt['fixtures'].append({'kind': kind, 'command': ' '.join(command),
                'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                'log_sha256': sha(log), 'result': str(result.relative_to(ROOT)),
                'result_sha256': sha(result)})
        path = ROOT / 'native' / f'physical-{suffix}-receipt.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(path.relative_to(ROOT)),
                                         'sha256': sha(path)}
        print('PHYSICAL', suffix, flush=True)
    save(manifest)


def compatibility():
    manifest = load()
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        for candidate in ('primary', 'fallback1'):
            output = REPO / '.runtime-work' / 'c183394' / ('civil-compat-' + suffix + '-' + candidate)
            bound = ROOT / 'compatibility' / (short(suffix) + '-' + candidate)
            bound.mkdir(parents=True, exist_ok=True)
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            old = bound / 'compatibility.json'
            current = False
            if old.is_file() and (bound / 'analysis.log').is_file() and (bound / 'negative.log').is_file():
                receipt = json.loads(old.read_text())
                current = (receipt.get('passed') is True and
                    receipt.get('construction_sha256') == selected['construction_sha256'] and
                    receipt.get('measurement_contract_sha256') == sha(ROOT / entry['measurement_contract']) and
                    receipt.get('analysis_sha256') == sha(ROOT / 'native/finalize.py') and
                    receipt.get('measurement_keys') == sorted(
                        row['output_key'] for row in json.loads((ROOT / entry['measurement_contract']).read_text())['requirements']))
            if current:
                selected['compatibility'] = {'receipt': str(old.relative_to(ROOT)),
                    'sha256': sha(old), 'log': str((bound / 'analysis.log').relative_to(ROOT)),
                    'negative_log': str((bound / 'negative.log').relative_to(ROOT))}
                print('REUSE COMPAT', suffix, candidate, flush=True)
                continue
            if output.exists():
                shutil.rmtree(output)
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output),
                       '--library', str(REPO / 'runtime/library'), '--validator',
                       str(REPO / '.runtime-work/c183394/decoder/.lake/build/bin/adapterCheck')]
            run(command, output=bound / 'command.log')
            for source, target in (('compatibility.json', 'compatibility.json'),
                                   ('compatibility-analysis.log', 'analysis.log'),
                                   ('negative-analysis.log', 'negative.log')):
                shutil.copyfile(output / source, bound / target)
            selected['compatibility'] = {'receipt': str((bound / 'compatibility.json').relative_to(ROOT)),
                'sha256': sha(bound / 'compatibility.json'),
                'log': str((bound / 'analysis.log').relative_to(ROOT)),
                'negative_log': str((bound / 'negative.log').relative_to(ROOT))}
            print('COMPAT', suffix, candidate, flush=True)
    save(manifest)


def bind():
    manifest = load()
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        case = entry['case_id']
        entry['post_capture'] = {'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_scope': 'Source-shaped diagnostic saved-only processing; no Native or optical acceptance'}
    save(manifest)
    print('BIND seven public compatibility receipts and post-capture commands', flush=True)


def saved():
    manifest = load()
    for suffix in SUFFIXES:
        entry = find(manifest, suffix)
        source = REPO / '.runtime-work' / 'c183394' / ('civil-compat-' + suffix + '-primary')
        attempt = REPO / '.runtime-work' / 'c183394' / ('civil-saved-attempt-' + suffix)
        output = REPO / '.runtime-work' / 'c183394' / ('civil-saved-' + suffix)
        for path in (attempt, output):
            if path.exists():
                shutil.rmtree(path)
        shutil.copytree(source, attempt)
        selection = attempt / 'candidate-selection.json'
        value = json.loads(selection.read_text())
        value['manifest_sha256'] = sha(MANIFEST)
        selection.write_text(json.dumps(value, indent=2) + '\n')
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'process-saved', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'), '--validator',
                   str(REPO / '.runtime-work/c183394/decoder/.lake/build/bin/adapterCheck')]
        folder = ROOT / 'saved-proof' / short(suffix)
        folder.mkdir(parents=True, exist_ok=True)
        run(command, output=folder / 'command.log')
        receipt = output / 'v0001/processing.json'
        if not json.loads(receipt.read_text()).get('passed'):
            raise ValueError('Saved-only receipt failed: ' + suffix)
        shutil.copyfile(receipt, folder / 'processing.json')
        entry['post_capture'].update(test_exit_code=0,
            test_log=str((folder / 'processing.json').relative_to(ROOT)),
            test_log_sha256=sha(folder / 'processing.json'))
        print('SAVED', suffix, flush=True)
        save(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('sync', 'offline', 'physical', 'compatibility',
                                          'bind', 'saved'))
    globals()[parser.parse_args().stage]()
