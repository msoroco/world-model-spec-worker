"""Reprove all selected compatibility and saved processing against final manifest."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PROPOSAL = HERE / 'proposals/cases.json'
PYTHON = ROOT / '.venv-cpu/bin/python'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def execute(command, log):
    with log.open('w') as stream:
        outcome = subprocess.run(command, cwd=ROOT, stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=600)
    if outcome.returncode:
        raise RuntimeError(f'{shlex.join(command)} failed {outcome.returncode}; see {log}')


def one(entry, candidate, manifest_sha, proposal_sha):
    case_id = entry['case_id']
    suffix = case_id.rsplit('__', 1)[-1]
    selected = (entry if candidate == 'primary' else
                next(row for row in entry['candidates'] if row['id'] == candidate))
    stem = f'c104538-update027-{suffix}-{candidate}'
    if suffix == 'below_500_ft' and candidate == 'primary':
        stem = 'c104538-update027-below-primary'
    attempt = ROOT / '.runtime-work' / (stem + '-compat')
    saved = ROOT / '.runtime-work' / (stem + '-saved')
    log_stem = f'update027-{suffix}-{candidate}'
    if suffix == 'below_500_ft' and candidate == 'primary':
        log_stem = 'update027-below-primary'
    compat_log = HERE / (log_stem + '-compat.log')
    saved_log = HERE / (log_stem + '-saved.log')
    if candidate == 'primary':
        compat_command = [str(PYTHON), str(ROOT/'runtime.py'), 'compatibility',
                          '--manifest', str(MANIFEST), '--case', case_id,
                          '--candidate', candidate, '--output', str(attempt),
                          '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    else:
        compat_command = [str(PYTHON), str(HERE/'candidate_compatibility.py'),
                          '--manifest', str(MANIFEST), '--case', case_id,
                          '--candidate', candidate,
                          '--recipe', str(HERE/f'update015-{suffix}-{candidate}-recipe.json'),
                          '--output', str(attempt), '--library', str(LIBRARY),
                          '--validator', str(VALIDATOR)]
    saved_command = [str(PYTHON), str(ROOT/'runtime.py'), 'process-saved',
                     '--manifest', str(MANIFEST), '--case', case_id,
                     '--attempt', str(attempt), '--output', str(saved),
                     '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    if not (attempt/'compatibility.json').is_file():
        if attempt.exists():
            raise RuntimeError(f'Partial compatibility output: {attempt}')
        execute(compat_command, compat_log)
    if not (saved/'v0001/processing.json').is_file():
        if saved.exists():
            raise RuntimeError(f'Partial saved output: {saved}')
        execute(saved_command, saved_log)
    selection = read(attempt/'candidate-selection.json')
    compatibility = read(attempt/'compatibility.json')
    processing = read(saved/'v0001/processing.json')
    if (selection.get('manifest_sha256') != manifest_sha or
            selection.get('construction_sha256') != selected['construction_sha256'] or
            selection.get('case_id') != case_id or
            selection.get('candidate_id') != candidate or
            compatibility.get('passed') is not True or
            compatibility.get('construction_sha256') != selected['construction_sha256'] or
            processing.get('passed') is not True or
            processing.get('originals_preserved') is not True or
            processing.get('missing_evidence') is not False or
            processing.get('case_id') != case_id or
            processing.get('candidate_id') != candidate or
            processing.get('native_revision', {}).get('construction_sha256') !=
                selected['construction_sha256']):
        raise ValueError(f'Current selected proof binding differs: {case_id} {candidate}')
    if not compat_log.is_file() or not saved_log.is_file():
        raise ValueError(f'Fresh proof log absent: {case_id} {candidate}')
    target = HERE/'update027-selected-proofs'/suffix/candidate
    target.mkdir(parents=True, exist_ok=True)
    for source, name in ((attempt/'candidate-selection.json', 'candidate-selection.json'),
                         (attempt/'compatibility.json', 'compatibility.json'),
                         (attempt/'compatibility-analysis.log', 'analysis.log'),
                         (attempt/'negative-analysis.log', 'negative.log'),
                         (saved/'v0001/processing.json', 'processing.json')):
        shutil.copyfile(source, target/name)
    return {'case_id': case_id, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'manifest_sha256': manifest_sha, 'proposal_sha256': proposal_sha,
            'compatibility_command': shlex.join(compat_command),
            'saved_command': shlex.join(saved_command),
            'compatibility_log': compat_log.name, 'compatibility_log_sha256': sha(compat_log),
            'saved_log': saved_log.name, 'saved_log_sha256': sha(saved_log),
            'proofs': {name: sha(target/name) for name in
                       ('candidate-selection.json', 'compatibility.json', 'analysis.log',
                        'negative.log', 'processing.json')},
            'synthetic_diagnostic': True, 'original_native_proven': False}


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Pinned Lean validator absent')
    manifest_sha, proposal_sha = sha(MANIFEST), sha(PROPOSAL)
    manifest = read(MANIFEST)
    if manifest['selection_review']['proposal_sha256'] != proposal_sha:
        raise ValueError('Selected manifest proposal binding changed')
    tasks = [(entry, candidate) for entry in manifest['cases'] for candidate in CANDIDATES]
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(one, entry, candidate, manifest_sha, proposal_sha):
                   (entry['case_id'], candidate) for entry, candidate in tasks}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(row['case_id'].rsplit('__', 1)[-1], row['candidate_id'], 'passed', flush=True)
    if sha(MANIFEST) != manifest_sha or sha(PROPOSAL) != proposal_sha:
        raise ValueError('Manifest/proposal changed during matrix proof')
    rows.sort(key=lambda row: (row['case_id'], CANDIDATES.index(row['candidate_id'])))
    summary = {'format': 'c104538-final-manifest-matrix-v1',
               'manifest_sha256': manifest_sha, 'proposal_sha256': proposal_sha,
               'results': rows, 'original_native_proven': False,
               'physical_or_legal_acceptance': False}
    path = HERE/'update027-final-manifest-matrix.json'
    path.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'candidate_proofs': len(rows), 'summary_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
