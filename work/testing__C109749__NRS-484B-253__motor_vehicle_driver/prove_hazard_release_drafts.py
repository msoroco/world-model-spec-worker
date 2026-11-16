"""Run exact CPU diagnostics for unselected release-grid constructions."""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
STAGE = REPO / '.runtime-work/c109749-hazard-release-stage-v2'
MANIFEST = STAGE / 'work' / ROOT.name / 'hazard-release-draft-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        subprocess.run([str(arg) for arg in args], cwd=REPO, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove():
    index = json.loads((ROOT / 'hazard-release-draft-index.json').read_text())
    output = []
    for case in index['cases']:
        case_id = case['case_id']
        suffix = case_id.split('__')[-1]
        for variant in case['variants']:
            label = variant['id']
            candidate = [] if label == 'primary' else ['--candidate', label]
            stem = suffix + '-' + label
            proof = ROOT / 'cases' / suffix / 'draft-proofs' / label
            run([PYTHON, REPO / 'runtime.py', 'offline', '--manifest', MANIFEST,
                 '--case', case_id, '--output', STAGE / '.runtime-work' / (stem + '-offline')]
                + candidate, proof / 'offline.log')
            compat = STAGE / '.runtime-work' / (stem + '-compat')
            run([PYTHON, REPO / 'runtime.py', 'compatibility', '--manifest', MANIFEST,
                 '--case', case_id, '--output', compat, '--library', REPO / 'runtime/library',
                 '--validator', VALIDATOR] + candidate, proof / 'compatibility.log')
            saved = STAGE / '.runtime-work' / (stem + '-saved')
            run([PYTHON, REPO / 'runtime.py', 'process-saved', '--manifest', MANIFEST,
                 '--case', case_id, '--attempt', compat, '--output', saved,
                 '--library', REPO / 'runtime/library', '--validator', VALIDATOR],
                proof / 'saved.log')
            for source, name in ((compat / 'compatibility.json', 'compatibility.json'),
                                 (compat / 'negative-analysis.log', 'negative-analysis.log'),
                                 (saved / 'v0001/processing.json', 'processing.json')):
                shutil.copy2(source, proof / name)
            output.append({'case_id': case_id, 'candidate': label,
                           'construction_sha256': variant['construction_sha256'],
                           'offline_log_sha256': sha(proof / 'offline.log'),
                           'compatibility_receipt_sha256': sha(proof / 'compatibility.json'),
                           'negative_log_sha256': sha(proof / 'negative-analysis.log'),
                           'saved_receipt_sha256': sha(proof / 'processing.json'),
                           'saved_log_sha256': sha(proof / 'saved.log'),
                           'scope': 'isolated synthetic software diagnostic; unselected'})
    path = ROOT / 'hazard-release-draft-proof-index.json'
    path.write_text(json.dumps({'format': 'worker-hazard-release-draft-proofs',
                                'cases': output}, indent=2) + '\n')
    return len(output)


def prove_canonical(suffix, label, tag):
    """Replay one selected variant against the current execution manifest."""
    assert suffix in ('approaching_release_3s', 'approaching_release_5s')
    assert label in ('primary', 'fallback1', 'fallback2', 'fallback3')
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case_id = ROOT.name + '__' + suffix
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    assert entry['kind'] == 'delivery'
    item = entry if label == 'primary' else next(
        candidate for candidate in entry['candidates'] if candidate['id'] == label)
    assert sha(ROOT / item['construction']) == item['construction_sha256']
    candidate = [] if label == 'primary' else ['--candidate', label]
    output = REPO / '.runtime-work' / ('c109749-release-canonical-' + tag) / (suffix + '-' + label)
    assert not output.exists(), 'Use a fresh ignored canonical proof output'
    proof = ROOT / 'cases' / suffix / 'draft-proofs' / label
    offline = [PYTHON, REPO / 'runtime.py', 'offline', '--manifest', manifest_path,
               '--case', case_id, '--output', output / 'offline', *candidate]
    run(offline, proof / 'offline.log')
    offline_log = json.loads((proof / 'offline.log').read_text())
    assert offline_log['offline_passed'] is True
    item['offline'] = {'command': shlex.join(map(str, offline)), 'exit_code': 0,
                       'log': str((proof / 'offline.log').relative_to(ROOT)),
                       'log_sha256': sha(proof / 'offline.log'),
                       'construction_sha256': item['construction_sha256']}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    compat = output / 'compatibility'
    command = [PYTHON, REPO / 'runtime.py', 'compatibility', '--manifest', manifest_path,
               '--case', case_id, '--output', compat, '--library', REPO / 'runtime/library',
               '--validator', VALIDATOR, *candidate]
    run(command, output / 'compatibility-command.log')
    for source, name in (('compatibility.json', 'compatibility.json'),
                         ('compatibility-analysis.log', 'compatibility.log'),
                         ('negative-analysis.log', 'negative-analysis.log')):
        shutil.copy2(compat / source, proof / name)
    receipt = json.loads((proof / 'compatibility.json').read_text())
    assert receipt['passed'] is True and receipt['case_id'] == case_id
    assert receipt['candidate_id'] == label and receipt['construction_sha256'] == item['construction_sha256']
    assert receipt['log_sha256'] == sha(proof / 'compatibility.log')
    assert receipt['negative_log_sha256'] == sha(proof / 'negative-analysis.log')
    assert b'Missing required source: interaction_history.jsonl' in (proof / 'negative-analysis.log').read_bytes()
    item['compatibility'] = {
        'receipt': str((proof / 'compatibility.json').relative_to(ROOT)),
        'sha256': sha(proof / 'compatibility.json'),
        'log': str((proof / 'compatibility.log').relative_to(ROOT)),
        'negative_log': str((proof / 'negative-analysis.log').relative_to(ROOT)),
        'replay_command': shlex.join(map(str, command)),
        'replay_log': str((output / 'compatibility-command.log').relative_to(REPO)),
    }
    item['negative'] = {'log': str((proof / 'negative-analysis.log').relative_to(ROOT))}
    saved = output / 'saved'
    command = [PYTHON, REPO / 'runtime.py', 'process-saved', '--manifest', manifest_path,
               '--case', case_id, '--attempt', compat, '--output', saved,
               '--library', REPO / 'runtime/library', '--validator', VALIDATOR]
    run(command, proof / 'saved.log')
    shutil.copy2(saved / 'v0001/processing.json', proof / 'processing.json')
    processing = json.loads((proof / 'processing.json').read_text())
    assert processing['passed'] is True and processing['recorded_only'] is True
    assert processing['originals_preserved'] is True
    assert processing['analysis_revision']['construction_sha256'] == item['construction_sha256']
    item['post_capture'] = {
        'recorded_only': True, 'command': shlex.join(map(str, command)),
        'feedback_command': 'cat ' + str(saved / 'v0001/feedback.json'),
        'test_log': str((proof / 'saved.log').relative_to(ROOT)),
        'test_log_sha256': sha(proof / 'saved.log'), 'test_exit_code': 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    index_path = ROOT / 'hazard-release-draft-proof-index.json'
    index = json.loads(index_path.read_text())
    row = next(x for x in index['cases'] if x['case_id'] == case_id and x['candidate'] == label)
    row.update({'construction_sha256': item['construction_sha256'],
                'offline_log_sha256': sha(proof / 'offline.log'),
                'compatibility_receipt_sha256': sha(proof / 'compatibility.json'),
                'negative_log_sha256': sha(proof / 'negative-analysis.log'),
                'saved_receipt_sha256': sha(proof / 'processing.json'),
                'saved_log_sha256': sha(proof / 'saved.log'),
                'scope': 'selected exact current-manifest CPU software proof; synthetic source'})
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    return {'case_id': case_id, 'candidate': label,
            'construction_sha256': item['construction_sha256'],
            'compatibility_receipt_sha256': item['compatibility']['sha256'],
            'saved_receipt_sha256': sha(proof / 'processing.json'),
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 5 and sys.argv[1] == '--canonical':
        print(json.dumps(prove_canonical(sys.argv[2], sys.argv[3], sys.argv[4]), indent=2))
    else:
        print(prove())
