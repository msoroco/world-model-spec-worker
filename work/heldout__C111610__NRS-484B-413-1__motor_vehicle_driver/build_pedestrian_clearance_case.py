"""Construct and prove the exact farther-pedestrian turn variant from originals."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PY = str(REPO / '.venv-cpu/bin/python')
OLD = ROOT.name + '__pedestrian_horn_before_turn'
NEW = ROOT.name + '__pedestrian_farther_horn_before_turn'
BASE = 'pedestrian-farther-horn'
MANIFEST = ROOT / 'execution-manifest.json'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, content):
    path.write_text(content, encoding='utf-8')
    return digest(path)


def save(path, obj):
    return write(path, json.dumps(obj, indent=2) + '\n')


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def construction(source_name, target_name, *, candidate='primary'):
    data = json.loads((ROOT / source_name).read_text().replace(OLD, NEW))
    for item in data['files']:
        if item['path'] == 'runner.py':
            item['content'] = (ROOT / 'native_horn/runner.py').read_text().replace(OLD, NEW)
        elif item['path'] == 'turn_native_route.py':
            item['content'] = (ROOT / 'native_horn/turn_native_route.py').read_text()
        elif item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['engineering']['pedestrian_along_m'] = 5. if candidate == 'fallback1' else 6.
            config['engineering']['pedestrian_left_m'] = 13.5 if candidate == 'fallback1' else 14.
            item['content'] = json.dumps(config, indent=2) + '\n'
    return save(ROOT / target_name, data)


def main():
    manifest = json.loads(MANIFEST.read_text())
    source = next(item for item in manifest['cases'] if item['case_id'] == OLD)
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != NEW]
    primary_name = BASE + '-construction.json'
    primary_hash = construction(source['construction'], primary_name)

    diagnostic = json.loads((ROOT / 'pedestrian-horn-diagnostic.json').read_text())
    rows = [json.loads(line) for line in diagnostic['files']['participant_bodies.jsonl'].splitlines()]
    for row in rows:
        row['bodies']['ped_listener']['y_m'] += 12.
    diagnostic['files']['participant_bodies.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    diagnostic_name = BASE + '-diagnostic.json'
    diagnostic_hash = save(ROOT / diagnostic_name, diagnostic)
    recipe = json.loads((ROOT / 'pedestrian-horn-recipe.json').read_text().replace(OLD, NEW))
    for source_ref in recipe['sources']:
        source_ref['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
        source_ref['sha256'] = diagnostic_hash
    recipe['generator']['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
    recipe['generator']['sha256'] = diagnostic_hash
    recipe_name = BASE + '-recipe.json'
    save(ROOT / recipe_name, recipe)
    contract_name = BASE + '-measurement-contract.json'
    save(ROOT / contract_name, json.loads((ROOT / source['measurement_contract']).read_text().replace(OLD, NEW)))

    entry = {key: json.loads(json.dumps(value)) for key, value in source.items()
             if key not in ('offline', 'compatibility', 'negative', 'saved_processing',
                            'delivery_acceptance', 'post_capture', 'physical_preparation')}
    entry.update(case_id=NEW, construction=primary_name, construction_sha256=primary_hash,
                 measurement_contract=contract_name,
                 fixture_recipe='work/' + ROOT.name + '/' + recipe_name, candidates=[])
    manifest['cases'].append(entry)
    save(MANIFEST, manifest)

    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['cases'] = [item for item in plan['cases'] if item['case_id'] != NEW]
    variant = json.loads(json.dumps(next(item for item in plan['cases'] if item['case_id'] == OLD)))
    variant['case_id'] = NEW
    variant['purpose'] = ('Same sourced left-turn and horn protocol with a pedestrian 12 m farther '
                          'left of the selected approach; measure original body clearance without '
                          'presuming affectedness or legal safety.')
    variant['construction_state'] = 'primary_cpu_proved_fallbacks_pending'
    plan['cases'].append(variant)
    comparison_id = 'pedestrian_clearance_sweep'
    plan['comparisons'] = [item for item in plan['comparisons'] if item['comparison_id'] != comparison_id]
    plan['comparisons'].append({
        'comparison_id': comparison_id, 'case_ids': [OLD, NEW],
        'fixed_conditions': ['same selected connected turn, driver, vehicle, turn controller and horn protocol',
                             'same 20 Hz duration, four named cameras and independent listener acquisition'],
        'deliberate_differences': ['constructed pedestrian offset left of selected approach: 2 m versus 14 m']})
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required' and NEW not in disposition['case_ids']:
            disposition['case_ids'].append(NEW)
    save(plan_path, plan)
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposals['cases'] = [item for item in proposals['cases'] if item['case_id'] != NEW]
    original_proposal = next(item for item in proposals['cases'] if item['case_id'] == OLD)
    proposals['cases'].append(json.loads(json.dumps(original_proposal).replace(OLD, NEW)))
    save(proposals_path, proposals)

    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if candidate == 'primary':
            target = entry
        else:
            source_candidate = next(item for item in source['candidates'] if item['id'] == candidate)
            name = BASE + '-' + candidate + '-construction.json'
            construction_hash = construction(source_candidate['construction'], name, candidate=candidate)
            target = {'id': candidate, 'construction': name,
                      'construction_sha256': construction_hash,
                      'trigger': source_candidate['trigger'],
                      'changed_knobs': source_candidate['changed_knobs']}
            if candidate == 'fallback1':
                target['changed_knobs'] = ['pedestrian approach-relative offset 6/14 to 5/13.5 m']
            entry['candidates'].append(target)
            save(MANIFEST, manifest)
        stem = BASE + '-' + candidate
        offline = [PY, 'runtime.py', 'offline', '--manifest', str(MANIFEST.relative_to(REPO)),
                   '--case', NEW, '--candidate', candidate,
                   '--output', '.runtime-work/c111610-' + stem + '-offline-v4', '--python', PY]
        offline_log = ROOT / (stem + '-offline.log')
        run(offline, offline_log)
        target['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                             'log': offline_log.name, 'log_sha256': digest(offline_log),
                             'construction_sha256': target['construction_sha256']}
        save(MANIFEST, manifest)
        output = REPO / ('.runtime-work/c111610-' + stem + '-compat-v4')
        compatibility = [PY, 'runtime.py', 'compatibility', '--manifest', str(MANIFEST.relative_to(REPO)),
                         '--case', NEW, '--candidate', candidate,
                         '--output', str(output.relative_to(REPO)), '--library', 'runtime/library',
                         '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        run(compatibility, ROOT / (stem + '-compatibility.log'))
        receipt = ROOT / (stem + '-receipt.json')
        analysis = ROOT / (stem + '-analysis.log')
        negative = ROOT / (stem + '-negative.log')
        for source_name, target_path in [('compatibility.json', receipt),
                                         ('compatibility-analysis.log', analysis),
                                         ('negative-analysis.log', negative)]:
            shutil.copy2(output / source_name, target_path)
        if not json.loads(receipt.read_text())['passed']:
            raise ValueError('Exact source compatibility failed: ' + candidate)
        target['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt),
                                   'log': analysis.name, 'negative_log': negative.name}
        if candidate == 'primary':
            entry['negative'] = {'log': negative.name}
        save(MANIFEST, manifest)
        print(candidate, 'offline and source-positive/negative compatibility passed', flush=True)
        if candidate != 'primary':
            continue
        attempt = REPO / '.runtime-work/c111610-pedestrian-farther-saved-attempt-v4'
        materialize(MANIFEST, NEW, attempt)
        with tempfile.TemporaryDirectory(prefix='c111610-farther-source-', dir=REPO / '.runtime-work') as temp:
            fixture = Path(temp) / 'fixture'
            materialize_fixture(REPO, ROOT / recipe_name, fixture)
            for item in fixture.iterdir():
                destination = attempt / item.name
                if destination.exists():
                    raise ValueError('Diagnostic source shadows construction: ' + item.name)
                if item.is_dir():
                    shutil.copytree(item, destination)
                else:
                    shutil.copy2(item, destination)
        saved_output = REPO / '.runtime-work/c111610-pedestrian-farther-saved-v4'
        saved = [PY, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
                 '--case', NEW, '--attempt', str(attempt.relative_to(REPO)),
                 '--output', str(saved_output.relative_to(REPO)), '--library', 'runtime/library',
                 '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        saved_log = ROOT / (BASE + '-saved.log')
        run(saved, saved_log)
        saved_receipt = ROOT / (BASE + '-saved-receipt.json')
        shutil.copy2(saved_output / 'v0001/processing.json', saved_receipt)
        summary = json.loads(saved_receipt.read_text())
        if not (summary['passed'] and summary['originals_preserved'] and not summary['missing_evidence']):
            raise ValueError('Farther-pedestrian saved source processing failed')
        entry['saved_processing'] = {'command': ' '.join(saved), 'exit_code': 0,
                                     'log': saved_log.name, 'log_sha256': digest(saved_log),
                                     'receipt': saved_receipt.name, 'receipt_sha256': digest(saved_receipt)}
        save(MANIFEST, manifest)
        print('primary saved processing passed', flush=True)


if __name__ == '__main__':
    main()
