"""Select the integrated reference bundle and bind its CPU diagnostics."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SELECTED = HERE / 'execution-manifest.json'
DRAFT = HERE / 'update153-integrated-all-text1-manifest.json'
PROPOSAL = HERE / 'proposals/cases.json'
SHORT = 'reference'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def relative(path):
    return str(path.relative_to(HERE))


def make_physical(entry):
    target = HERE / 'selected-physical-preparation/reference-integrated'
    target.mkdir(parents=True, exist_ok=True)
    fixtures = []
    lifecycle = None
    for kind in KINDS:
        result = target / (kind + '.json')
        log = target / (kind + '.log')
        if result.exists() or log.exists():
            raise ValueError('Retain prior physical fixture')
        command = [sys.executable, str(HERE / 'run_physical_fixture.py'),
                   '--manifest', str(DRAFT), '--case', entry['case_id'],
                   '--kind', kind, '--output', str(result)]
        process = subprocess.run(command, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write_text(process.stdout)
        if process.returncode:
            raise RuntimeError(f'{kind}: {process.stdout}')
        row = {'command': ' '.join(command), 'exit_code': process.returncode,
               'log': relative(log), 'log_sha256': sha(log),
               'result': relative(result), 'result_sha256': sha(result)}
        if kind == 'lifecycle':
            lifecycle = dict(row, events=EVENTS)
        else:
            fixtures.append(dict(row, kind=kind))
    receipt = target / 'proof.json'
    write(receipt, {'format': 'c183370-selected-physical-cpu-fixtures-v1',
                    'case_id': entry['case_id'],
                    'construction_sha256': entry['construction_sha256'],
                    'fixtures': fixtures, 'lifecycle': lifecycle,
                    'fixtures_are_cpu_mocks': True,
                    'original_native_motion_verified': False})
    return {'receipt': relative(receipt), 'sha256': sha(receipt)}


def make_candidate(entry, selected, candidate):
    stem = 'update154-integrated-text1-' + SHORT + '-' + candidate
    proof = read(HERE / (stem + '-proof.json'))
    if (proof['case_id'] != entry['case_id'] or
            proof['candidate_id'] != candidate or
            proof['construction_sha256'] != selected['construction_sha256'] or
            proof['manifest_sha256'] != sha(DRAFT) or
            proof['diagnostic_delivery_accepted'] is not False):
        raise ValueError('Integrated candidate proof differs: ' + candidate)
    for kind, expected in proof['logs'].items():
        if sha(HERE / (stem + '-' + kind + '.log')) != expected:
            raise ValueError('Integrated candidate log changed: ' + candidate)
    source = REPO / '.runtime-work' / (stem + '-compat')
    target = HERE / 'selected-proof-receipts/reference-integrated' / candidate
    target.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in (('compatibility.json', 'compatibility.json'),
                               ('compatibility-analysis.log', 'analysis.log'),
                               ('negative-analysis.log', 'negative.log')):
        dst = target / dst_name
        if dst.exists():
            raise ValueError('Retain prior compatibility receipt')
        shutil.copy2(source / src_name, dst)
    receipt = read(target / 'compatibility.json')
    if (receipt.get('passed') is not True or
            receipt['construction_sha256'] != selected['construction_sha256'] or
            sha(target / 'compatibility.json') != proof['compatibility_sha256'] or
            sha(target / 'analysis.log') != receipt['log_sha256'] or
            sha(target / 'negative.log') != receipt['negative_log_sha256']):
        raise ValueError('Compatibility receipt mismatch: ' + candidate)
    selected['compatibility'] = {
        'receipt': relative(target / 'compatibility.json'),
        'sha256': sha(target / 'compatibility.json'),
        'log': relative(target / 'analysis.log'),
        'negative_log': relative(target / 'negative.log')}
    log = HERE / (stem + '-offline.log')
    selected['offline'] = {
        'command': ('.venv-cpu/bin/python runtime.py offline --manifest '
                    f'work/{HERE.name}/execution-manifest.json --case '
                    f'{entry["case_id"]} --candidate {candidate} '
                    '--output ${OFFLINE_DIR} --python "$PWD/.venv-cpu/bin/python"'),
        'construction_sha256': selected['construction_sha256'],
        'exit_code': 0, 'log': relative(log), 'log_sha256': sha(log)}
    if candidate == 'primary':
        entry['negative'] = {'log': relative(target / 'negative.log'),
                             'log_sha256': sha(target / 'negative.log')}
        entry['post_capture']['test_exit_code'] = 0
        saved = HERE / (stem + '-saved.log')
        entry['post_capture']['test_log'] = relative(saved)
        entry['post_capture']['test_log_sha256'] = sha(saved)


def main():
    old = read(SELECTED)
    draft = read(DRAFT)
    proposal = read(PROPOSAL)
    if sha(SELECTED) != '75b3f478c31787dff5dd613f34972e1f377b4d84d781b974ad752b06528580b6':
        raise ValueError('Selected manifest changed; review promotion again')
    if sha(DRAFT) != '093a0fa3511b2b7e50827b823180765098b4b63c3d3247ab5ae44802137da365':
        raise ValueError('Integrated draft changed; review proof scope again')
    entry = next(e for e in old['cases'] if e['case_id'] == HERE.name + '__reference')
    integrated = next(e for e in draft['cases'] if e['case_id'] == entry['case_id'])
    old_entry = copy.deepcopy(entry)
    entry['construction'] = integrated['construction']
    entry['construction_sha256'] = integrated['construction_sha256']
    entry['candidates'] = copy.deepcopy(integrated['candidates'])
    entry['physical_preparation'] = make_physical(entry)
    for candidate in CANDIDATES:
        selected = entry if candidate == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == candidate)
        make_candidate(entry, selected, candidate)
    new_description = read(HERE / entry['construction'])['recording_description']
    proposal_case = next(c for c in proposal['cases'] if c['case_id'] == entry['case_id'])
    proposal_case['recording_description'] = new_description
    entry['candidate_offline_status'] = 'draft_proofs_bound_selected_hash_recheck_pending'
    entry['delivery_acceptance'] = {'case_id': entry['case_id'],
                                    'status': 'pending_integrated_selected_audit'}
    old_path = HERE / 'update154-selected-reference-before-integration.json'
    if old_path.exists():
        raise ValueError('Retain prior selected snapshot')
    write(old_path, {'entry': old_entry,
                     'manifest_sha256': sha(SELECTED),
                     'proposal_sha256': sha(PROPOSAL)})
    write(PROPOSAL, proposal)
    write(SELECTED, old)
    print(json.dumps({'case': entry['case_id'], 'manifest_sha256': sha(SELECTED),
                      'proposal_sha256': sha(PROPOSAL), 'ready': False}, sort_keys=True))


if __name__ == '__main__':
    main()
