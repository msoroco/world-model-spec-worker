"""Select the guarded far construction and reprove each exact CPU candidate."""
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1]
REPO = ASSIGNMENT.parent.parent
STAGE = HERE / 'clearance_guard'
MANIFEST = ASSIGNMENT / 'execution-manifest.json'
STAGED = ASSIGNMENT / 'clearance-guard-draft-manifest.json'
LABELS = ('primary', 'fallback1', 'fallback2', 'fallback3')
PYTHON = '.venv-cpu/bin/python'
MANIFEST_ARG = str(MANIFEST.relative_to(REPO))
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        subprocess.run(args, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def relative(path):
    return str(path.relative_to(ASSIGNMENT))


def promote():
    original = MANIFEST.read_bytes()
    manifest = json.loads(original)
    entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__approaching_far'))
    staged = json.loads(STAGED.read_text())['cases'][0]
    if entry['case_id'] != staged['case_id']:
        raise ValueError('Staged and selected cases differ')
    case = entry['case_id']
    try:
        for label in LABELS:
            selected = entry if label == 'primary' else next(x for x in entry['candidates'] if x['id'] == label)
            source = staged if label == 'primary' else next(x for x in staged['candidates'] if x['id'] == label)
            selected['construction'] = source['construction']
            selected['construction_sha256'] = source['construction_sha256']
        write(MANIFEST, manifest)
        for label in LABELS:
            selected = entry if label == 'primary' else next(x for x in entry['candidates'] if x['id'] == label)
            suffix = [] if label == 'primary' else ['--candidate', label]
            root = '.runtime-work/c109749-promoted-clearance-' + label
            offline = [PYTHON, 'runtime.py', 'offline', '--manifest', MANIFEST_ARG,
                       '--case', case, '--output', root + '-offline'] + suffix
            offline_log = STAGE / ('promoted-' + label + '-offline.log')
            run(offline, offline_log)
            selected['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                'log': relative(offline_log), 'log_sha256': sha(offline_log),
                'construction_sha256': selected['construction_sha256']}
            compat = [PYTHON, 'runtime.py', 'compatibility', '--manifest', MANIFEST_ARG,
                      '--case', case, '--output', root + '-compat', '--library',
                      'runtime/library', '--validator', VALIDATOR] + suffix
            compat_log = STAGE / ('promoted-' + label + '-compatibility.log')
            run(compat, compat_log)
            compat_root = REPO / (root + '-compat')
            proof_dir = STAGE / 'promoted-proofs' / label
            proof_dir.mkdir(parents=True, exist_ok=True)
            for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
                destination = ('exact-compatibility-analysis.log' if name == 'compatibility-analysis.log' else name)
                shutil.copy2(compat_root / name, proof_dir / destination)
            selected['compatibility'] = {'receipt': relative(proof_dir / 'compatibility.json'),
                'sha256': sha(proof_dir / 'compatibility.json'),
                'log': relative(proof_dir / 'exact-compatibility-analysis.log'),
                'negative_log': relative(proof_dir / 'negative-analysis.log'),
                'replay_command': ' '.join(compat), 'replay_log': relative(compat_log)}
            selected['negative'] = {'log': relative(proof_dir / 'negative-analysis.log')}
            saved = [PYTHON, 'runtime.py', 'process-saved', '--manifest', MANIFEST_ARG,
                     '--case', case, '--attempt', root + '-compat', '--output',
                     root + '-saved', '--library', 'runtime/library', '--validator', VALIDATOR]
            saved_log = STAGE / ('promoted-' + label + '-saved.log')
            run(saved, saved_log)
            saved_path = REPO / (root + '-saved') / 'v0001/processing.json'
            shutil.copy2(saved_path, proof_dir / 'processing.json')
            selected['post_capture'] = {'recorded_only': True, 'command': ' '.join(saved),
                'feedback_command': 'cat ' + root + '-saved/v0001/feedback.json',
                'test_log': relative(saved_log), 'test_log_sha256': sha(saved_log),
                'test_exit_code': 0}
            write(MANIFEST, manifest)
        physical = copy.deepcopy(json.loads((HERE / 'physical-proofs/receipt.json').read_text()))
        physical['construction_sha256'] = entry['construction_sha256']
        for fixture in physical['fixtures'] + [physical['lifecycle']]:
            kind = fixture.get('kind', 'lifecycle')
            output = STAGE / 'promoted-physical' / (kind + '.json')
            log = STAGE / 'promoted-physical' / (kind + '.log')
            command = [PYTHON, str((ASSIGNMENT / 'inside_physical_fixture_proof.py').relative_to(REPO)),
                       '--manifest', MANIFEST_ARG, '--case', case, '--kind', kind,
                       '--output', str(output.relative_to(REPO))]
            if kind == 'lifecycle':
                command += ['--saved-receipt', str((STAGE / 'promoted-proofs/primary/processing.json').relative_to(REPO))]
            run(command, log)
            fixture.update(command=' '.join(command), exit_code=0,
                           log=relative(log), log_sha256=sha(log),
                           result=relative(output), result_sha256=sha(output))
        physical_path = STAGE / 'promoted-physical/receipt.json'
        write(physical_path, physical)
        entry['physical_preparation'] = {'receipt': relative(physical_path), 'sha256': sha(physical_path)}
        delivery = entry['delivery_acceptance']
        delivery['command'] = (PYTHON + ' ' + str((ASSIGNMENT / 'far_delivery_fixture_proof.py').relative_to(REPO)) +
            ' --case ' + case + ' --output-root .runtime-work/c109749-clearance-guard-far-delivery'
            ' --media-root .runtime-work/c109749-far-media-v1')
        delivery['test_log'] = relative(STAGE / 'delivery-positive.log')
        delivery['test_log_sha256'] = sha(STAGE / 'delivery-positive.log')
        delivery['negative_command'] = (PYTHON + ' ' + str((ASSIGNMENT / 'far_delivery_fixture_proof.py').relative_to(REPO)) +
            ' --case ' + case + ' --output-root .runtime-work/c109749-clearance-guard-far-delivery-negative'
            ' --negative-source-root .runtime-work/c109749-clearance-guard-far-delivery')
        delivery['negative_log'] = relative(STAGE / 'delivery-negative.log')
        delivery['negative_log_sha256'] = sha(STAGE / 'delivery-negative.log')
        write(MANIFEST, manifest)
        run([PYTHON, str((ASSIGNMENT / 'validate_manifest.py').relative_to(REPO))],
            STAGE / 'promoted-manifest-validation.log')
    except Exception:
        MANIFEST.write_bytes(original)
        raise
    return {'case_id': case, 'candidate_count': len(LABELS),
            'manifest_sha256': sha(MANIFEST), 'physical_receipt_sha256': sha(physical_path)}


if __name__ == '__main__':
    print(json.dumps(promote(), sort_keys=True))
