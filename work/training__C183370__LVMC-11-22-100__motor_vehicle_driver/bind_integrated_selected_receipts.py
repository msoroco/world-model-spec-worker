"""Bind proven selected CPU receipts after all 48 integrated chains finish."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
LABELS = {
    'reference': 'update156-integrated',
    'contrast': 'update157-integrated',
    'barrier_crossing': 'update157-barrier',
    'barrier_avoidance': 'update157-barrier',
    'warning_sign_crossing': 'update157-warning',
    'warning_sign_avoidance': 'update157-warning',
    'highway_closed_sign_crossing': 'update157-highway',
    'highway_closed_sign_avoidance': 'update157-highway',
    'employee_exception_employee_crossing': 'update156-integrated',
    'employee_exception_nonemployee_crossing': 'update156-integrated',
    'newly_laid_crossing': 'update157-newlylaid',
    'newly_laid_avoidance': 'update157-newlylaid',
}
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(HERE))


def copy_new(source, destination):
    if destination.exists():
        raise ValueError('Retain existing receipt: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def checked_proof(entry, candidate, short, label, manifest_sha):
    stem = f'{label}-{short}-{candidate}'
    proof_path = HERE / (stem + '-proof.json')
    proof = json.loads(proof_path.read_text())
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    if (proof['case_id'] != entry['case_id'] or proof['candidate_id'] != candidate
            or proof['manifest_sha256'] != manifest_sha
            or proof['construction_sha256'] != selected['construction_sha256']
            or proof['diagnostic_delivery_accepted'] is not False
            or proof['original_native_verified'] is not False):
        raise ValueError('Selected proof does not bind this manifest: ' + stem)
    for kind, digest in proof['logs'].items():
        if sha(HERE / (stem + '-' + kind + '.log')) != digest:
            raise ValueError('Selected proof log changed: ' + stem + '/' + kind)
    generated = ROOT / '.runtime-work' / ('c183370-' + stem + '-compat')
    if sha(generated / 'compatibility.json') != proof['compatibility_sha256']:
        raise ValueError('Selected compatibility output changed: ' + stem)
    saved = ROOT / '.runtime-work' / ('c183370-' + stem + '-saved/v0001/processing.json')
    if sha(saved) != proof['saved_sha256']:
        raise ValueError('Selected saved output changed: ' + stem)
    processed = json.loads(saved.read_text())
    if (processed['passed'] is not True or processed['recorded_only'] is not True
            or processed['timestamp_joins']['frames'] != 600):
        raise ValueError('Selected saved processing incomplete: ' + stem)
    return stem, generated


def bind_candidate(entry, selected, candidate, short, label, manifest_sha):
    stem, generated = checked_proof(entry, candidate, short, label, manifest_sha)
    target = HERE / 'selected-proof-receipts' / (short + '-integrated-current') / candidate
    analysis = target / 'analysis.log'
    negative = target / 'negative.log'
    receipt = target / 'compatibility.json'
    copy_new(generated / 'compatibility-analysis.log', analysis)
    copy_new(generated / 'negative-analysis.log', negative)
    copy_new(generated / 'compatibility.json', receipt)
    offline_log = HERE / (stem + '-offline.log')
    selected['offline'] = {
        'command': ('.venv-cpu/bin/python runtime.py offline --manifest '
                    f'work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} '
                    f'--candidate {candidate} --output ${{OFFLINE_DIR}} '
                    '--python "$PWD/.venv-cpu/bin/python"'),
        'construction_sha256': selected['construction_sha256'],
        'exit_code': 0, 'log': rel(offline_log), 'log_sha256': sha(offline_log),
    }
    selected['compatibility'] = {
        'receipt': rel(receipt), 'sha256': sha(receipt),
        'log': rel(analysis), 'negative_log': rel(negative),
    }
    if candidate == 'primary':
        entry['negative'] = {'log': rel(negative), 'log_sha256': sha(negative)}
        entry['post_capture']['test_exit_code'] = 0
        entry['post_capture']['test_log'] = rel(HERE / (stem + '-saved.log'))
        entry['post_capture']['test_log_sha256'] = sha(HERE / (stem + '-saved.log'))


def delivery_contract(entry, short):
    folder = HERE / 'selected-delivery-contracts' / (short + '-integrated-current')
    folder.mkdir(parents=True, exist_ok=False)
    script = HERE / 'run_delivery_contract_fixture.py'
    base = [sys.executable, str(script), '--case', entry['case_id']]
    logs = []
    for negative in (False, True):
        log = folder / ('negative.log' if negative else 'positive.log')
        completed = subprocess.run(base + (['--negative'] if negative else []),
                                   cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        log.write_text(completed.stdout)
        if (negative and completed.returncode == 0) or (not negative and completed.returncode != 0):
            raise ValueError('Delivery contract proof exit differs: ' + short)
        logs.append((log, completed.returncode))
    if 'Independent physical review bindings or checks incomplete' not in logs[1][0].read_text():
        raise ValueError('Delivery negative failed for another reason: ' + short)
    entry['delivery_acceptance'] = {
        'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
        'script': rel(script), 'script_sha256': sha(script),
        'command': f'.venv-cpu/bin/python work/{HERE.name}/run_delivery_contract_fixture.py --case {entry["case_id"]}',
        'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/run_delivery_contract_fixture.py --case {entry["case_id"]} --negative',
        'test_exit_code': logs[0][1], 'test_log': rel(logs[0][0]),
        'test_log_sha256': sha(logs[0][0]),
        'negative_exit_code': logs[1][1], 'negative_log': rel(logs[1][0]),
        'negative_log_sha256': sha(logs[1][0]),
        'negative_expected_error': 'Independent physical review bindings or checks incomplete',
    }


def main():
    manifest_sha = sha(MANIFEST)
    if manifest_sha != '08e4b7f1a894b68d881b04ca80bb1251a6994850a6d73334c79a5c913a180cea':
        raise ValueError('Selected manifest changed before binding')
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 12:
        raise ValueError('Expected twelve selected cases')
    # Verify the entire candidate inventory before creating return receipts.
    for entry in manifest['cases']:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        label = LABELS[short]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            checked_proof(entry, candidate, short, label, manifest_sha)
    snapshot = HERE / 'update157-before-receipt-binding.json'
    if snapshot.exists():
        raise ValueError('Retain previous manifest snapshot')
    snapshot.write_bytes(MANIFEST.read_bytes())
    for entry in manifest['cases']:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        label = LABELS[short]
        bind_candidate(entry, entry, 'primary', short, label, manifest_sha)
        for selected in entry['candidates']:
            bind_candidate(entry, selected, selected['id'], short, label, manifest_sha)
        entry['candidate_offline_status'] = 'all_four_integrated_cpu_receipts_bound; final_manifest_hash_reproof_pending'
        delivery_contract(entry, short)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cases': 12, 'candidates': 48,
                      'previous_manifest_sha256': manifest_sha,
                      'bound_manifest_sha256': sha(MANIFEST)}, sort_keys=True))


if __name__ == '__main__':
    main()
