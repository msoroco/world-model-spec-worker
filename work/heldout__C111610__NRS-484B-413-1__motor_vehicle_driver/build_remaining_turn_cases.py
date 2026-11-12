"""Adapt and prove the two remaining same-law turn signal branches."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT.parent / 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver'
OLD = SOURCE.name
NEW = ROOT.name
PY = str(REPO / '.venv-cpu/bin/python')
MANIFEST = ROOT / 'execution-manifest.json'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture

MAPPING = [
    ('vehicle_left_indicator', 'other_vehicle_signal_before_turn', 'vehicle-indicator'),
    ('both_signals', 'both_users_both_signals', 'both-signals'),
]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(data, encoding='utf-8')
    return digest(path)


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


source_manifest = json.loads((SOURCE / 'execution-manifest.json').read_text())
manifest = json.loads(MANIFEST.read_text())
proposals_path = ROOT / 'proposals/cases.json'
proposals = json.loads(proposals_path.read_text())
source_proposals = json.loads((SOURCE / 'proposals/cases.json').read_text())
requirement = json.loads((ROOT / 'case-plan.json').read_text())['requirement_dispositions'][0]['requirement']


def save():
    write(MANIFEST, json.dumps(manifest, indent=2) + '\n')


for old_suffix, new_suffix, base in MAPPING:
    old_case = OLD + '__' + old_suffix
    case = NEW + '__' + new_suffix
    source_entry = next(c for c in source_manifest['cases'] if c['case_id'] == old_case)

    def transform(source_name):
        return (SOURCE / source_name).read_text(encoding='utf-8').replace(old_case, case).replace(OLD, NEW).replace('C111603', 'C111610')

    construction_name = base + '-construction.json'
    construction_hash = write(ROOT / construction_name, transform(source_entry['construction']))
    diagnostic_name = base + '-diagnostic.json'
    diagnostic_hash = write(ROOT / diagnostic_name, transform(base + '-diagnostic.json'))
    recipe_name = base + '-recipe.json'
    recipe = json.loads(transform(base + '-recipe.json'))
    for source in recipe['sources']:
        source['sha256'] = diagnostic_hash
    recipe['generator']['sha256'] = diagnostic_hash
    write(ROOT / recipe_name, json.dumps(recipe, indent=2) + '\n')
    contract_name = base + '-measurement-contract.json'
    contract = json.loads(transform(source_entry['measurement_contract']))
    for item in contract['requirements']:
        item['disposition_index'] = 0
        item['requirement'] = requirement
    write(ROOT / contract_name, json.dumps(contract, indent=2) + '\n')
    proposal = next(c for c in source_proposals['cases'] if c['case_id'] == old_case)
    proposal = json.loads(json.dumps(proposal).replace(old_case, case).replace(OLD, NEW))
    proposals['cases'] = [c for c in proposals['cases'] if c['case_id'] != case] + [proposal]
    write(proposals_path, json.dumps(proposals, indent=2) + '\n')

    entry = {
        'case_id': case, 'kind': 'delivery', 'construction': construction_name,
        'construction_sha256': construction_hash,
        'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
        'measurement_contract': contract_name, 'fixture_recipe': f'work/{NEW}/{recipe_name}',
        'candidate_risk': source_entry['candidate_risk'], 'candidates': [],
        'native_handoff': source_entry['native_handoff'],
    }
    manifest['cases'] = [c for c in manifest['cases'] if c['case_id'] != case] + [entry]
    save()
    for candidate_id in ['primary', 'fallback1', 'fallback2', 'fallback3']:
        if candidate_id != 'primary':
            source_candidate = next(c for c in source_entry['candidates'] if c['id'] == candidate_id)
            candidate_name = base + '-' + candidate_id + '-construction.json'
            candidate_hash = write(ROOT / candidate_name, transform(source_candidate['construction']))
            target = {'id': candidate_id, 'construction': candidate_name,
                      'construction_sha256': candidate_hash,
                      'trigger': source_candidate['trigger'],
                      'changed_knobs': source_candidate['changed_knobs']}
            entry['candidates'].append(target)
            save()
        else:
            target = entry
        stem = base + '-' + candidate_id
        offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
                   '--case', case, '--candidate', candidate_id,
                   '--output', '.runtime-work/c111610-' + stem + '-offline-proof', '--python', PY]
        offline_log = ROOT / (stem + '-offline.log')
        run(offline, offline_log)
        target['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                             'log': offline_log.name, 'log_sha256': digest(offline_log),
                             'construction_sha256': target['construction_sha256']}
        save()
        output = REPO / ('.runtime-work/c111610-' + stem + '-compat-proof')
        compatibility = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
                         '--case', case, '--candidate', candidate_id,
                         '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
                         '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        run(compatibility, ROOT / (stem + '-compatibility.log'))
        receipt = ROOT / (stem + '-receipt.json')
        analysis = ROOT / (stem + '-analysis.log')
        negative = ROOT / (stem + '-negative.log')
        for name, path in [('compatibility.json', receipt),
                           ('compatibility-analysis.log', analysis),
                           ('negative-analysis.log', negative)]:
            shutil.copy2(output / name, path)
        assert json.loads(receipt.read_text())['passed']
        target['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                                   'log': analysis.name, 'negative_log': negative.name}
        if candidate_id == 'primary':
            target['negative'] = {'log': negative.name}
        save()
        print(new_suffix, candidate_id, 'offline and compatibility passed', flush=True)

    attempt = REPO / ('.runtime-work/c111610-' + base + '-saved-attempt-proof')
    materialize(MANIFEST, case, attempt)
    with tempfile.TemporaryDirectory(prefix='c111610-' + base + '-source-', dir=REPO / '.runtime-work') as temporary:
        fixture = Path(temporary) / 'fixture'
        materialize_fixture(REPO, ROOT / recipe_name, fixture)
        for source in fixture.iterdir():
            destination = attempt / source.name
            if destination.exists():
                raise ValueError('Diagnostic source shadows construction: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
    saved_output = REPO / ('.runtime-work/c111610-' + base + '-saved-proof')
    command = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
               '--case', case, '--attempt', str(attempt.relative_to(REPO)),
               '--output', str(saved_output.relative_to(REPO)), '--library', 'runtime/library',
               '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log = ROOT / (base + '-saved.log')
    run(command, log)
    receipt = ROOT / (base + '-saved-receipt.json')
    shutil.copy2(saved_output / 'v0001/processing.json', receipt)
    saved = json.loads(receipt.read_text())
    assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
    entry['saved_processing'] = {'command': ' '.join(command), 'exit_code': 0,
                                 'log': log.name, 'log_sha256': digest(log),
                                 'receipt': receipt.name, 'receipt_sha256': digest(receipt)}
    save()
    print(new_suffix, 'saved processing passed', flush=True)
