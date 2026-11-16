"""Stage and CPU-check the district capture gate for every selected candidate.

This keeps the current selected manifest and its existing proof hashes intact.
The staged bundles are ignored diagnostics until their full proof replay is bound.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
STAGE = ROOT / '.runtime-work' / os.environ.get(
    'C109749_DISTRICT_STAGE', 'c109749-district-rollout-stage-v2')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Expected one runner anchor, found {source.count(old)}: {old[:70]}')
    return source.replace(old, new, 1)


def transform(construction, audit_source, test_source):
    result = json.loads(json.dumps(construction))
    files = {item['path']: item for item in result['files']}
    if 'district_site_audit.py' in files or 'tests/test_district_integration.py' in files:
        raise ValueError('Selected construction already has district integration')
    runner = files['runner.py']['content']
    runner = replace_once(runner, 'import json\n', 'import json\nimport os\n')
    runner = replace_once(
        runner,
        'from native_scene import control_inputs, junction_context\n',
        'from native_scene import control_inputs, junction_context\n'
        'from district_site_audit import verify_district_site_packet\n',
    )
    binder = '''def bind_district_context(context, native_map_name, packet_path):
    """Require an independently source-reviewed, exact-junction district packet.

    A diagnostic packet can test software wiring but cannot authorize capture.
    Legal district classification remains for the local reviewer.
    """
    if not packet_path:
        raise ValueError('Reviewed district site packet path required for Native capture')
    review = verify_district_site_packet(context, native_map_name, packet_path)
    if review['diagnostic_only']:
        raise ValueError('Diagnostic district packet cannot authorize Native capture')
    context['district_source_review'] = review
    return context


'''
    runner = replace_once(
        runner, 'def camera_transforms(carla, selected, context):\n',
        binder + 'def camera_transforms(carla, selected, context):\n',
    )
    runner = replace_once(
        runner,
        "        context['native_map_id'] = world.get_map().name\n",
        "        context['native_map_id'] = world.get_map().name\n"
        "        context = bind_district_context(context, world.get_map().name,\n"
        "                                            os.environ.get('SCENARIO_DISTRICT_SITE_PACKET'))\n",
    )
    files['runner.py']['content'] = runner
    result['files'].append({'path': 'district_site_audit.py', 'content': audit_source})
    result['files'].append({'path': 'tests/test_district_integration.py', 'content': test_source})
    return result


def main():
    if STAGE.exists():
        raise ValueError(f'Retain existing stage; choose a new stage directory: {STAGE}')
    original = json.loads((FOLDER / 'execution-manifest.json').read_text())
    draft = json.loads((FOLDER / 'district-integration-draft-construction.json').read_text())
    draft_files = {item['path']: item['content'] for item in draft['files']}
    audit_source = (FOLDER / 'district_site_audit.py').read_text()
    assert audit_source == draft_files['district_site_audit.py']
    test_source = draft_files['tests/test_district_integration.py']
    STAGE.mkdir(parents=True)
    (STAGE / 'proposals').mkdir()
    shutil.copy2(FOLDER / 'case-plan.json', STAGE / 'case-plan.json')
    shutil.copy2(FOLDER / 'proposals/cases.json', STAGE / 'proposals/cases.json')
    entries = []
    summary = []
    for index, entry in enumerate(original['cases']):
        case = entry['case_id']
        staged_entry = json.loads(json.dumps(entry))
        contract = entry['measurement_contract']
        (STAGE / contract).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FOLDER / contract, STAGE / contract)
        selected = [('primary', entry)] + [
            (item['id'], item) for item in entry['candidates']
        ]
        if len(selected) != 4:
            raise ValueError(f'Expected primary and three fallbacks: {case}')
        for candidate_id, candidate in selected:
            source = FOLDER / candidate['construction']
            if digest(source) != candidate['construction_sha256']:
                raise ValueError(f'Current candidate hash mismatch: {case}/{candidate_id}')
            updated = transform(json.loads(source.read_text()), audit_source, test_source)
            if index == 0 and candidate_id == 'primary' and updated != draft:
                raise ValueError('Rollout transform diverges from the passing first-case draft')
            relative = f'bundles/{index:02d}-{candidate_id}.json'
            target = STAGE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(updated, indent=2) + '\n')
            selected_ref = {'construction': relative, 'construction_sha256': digest(target)}
            if candidate_id == 'primary':
                staged_entry.update(selected_ref)
            else:
                staged_candidate = next(item for item in staged_entry['candidates']
                                        if item['id'] == candidate_id)
                staged_candidate.update(selected_ref)
            summary.append({'case_id': case, 'candidate_id': candidate_id,
                            'original': candidate['construction'],
                            'staged': str(target.relative_to(ROOT)),
                            'construction_sha256': digest(target)})
        entries.append(staged_entry)
    manifest = STAGE / 'execution-manifest.json'
    manifest.write_text(json.dumps({'format': 'worker-execution-manifest',
                                    'assignment_id': original['assignment_id'],
                                    'runtime_manifest_sha256': original['runtime_manifest_sha256'],
                                    'cases': entries}, indent=2) + '\n')
    for index, item in enumerate(summary):
        attempt = STAGE / 'offline' / f'{index:02d}'
        command = [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest',
                   str(manifest), '--case', item['case_id'], '--candidate',
                   item['candidate_id'], '--output', str(attempt)]
        process = subprocess.run(command, cwd=ROOT, env={**os.environ,
                                 'PYTHONDONTWRITEBYTECODE': '1'},
                                 text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        item['offline_exit_code'] = process.returncode
        item['offline_log'] = str((attempt / 'offline.log').relative_to(ROOT)) if (attempt / 'offline.log').exists() else None
        item['offline_log_sha256'] = digest(attempt / 'offline.log') if (attempt / 'offline.log').exists() else None
        if process.returncode:
            (STAGE / 'failed-command.log').write_text(process.stdout)
            break
    proof = {'format': 'c109749-district-rollout-stage-v2',
             'source_manifest_sha256': digest(FOLDER / 'execution-manifest.json'),
             'stage_manifest_sha256': digest(manifest),
             'staged_candidates': len(summary),
             'offline_passed': sum(item.get('offline_exit_code') == 0 for item in summary),
             'candidates': summary,
             'selected_manifest_mutated': False,
             'physical_acceptance_claimed': False}
    (STAGE / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'stage': str(STAGE.relative_to(ROOT)),
                      'staged_candidates': len(summary),
                      'offline_passed': proof['offline_passed'],
                      'proof_sha256': digest(STAGE / 'proof.json')}))
    if proof['offline_passed'] != len(summary):
        raise SystemExit('Staged district rollout has failing offline proof')


if __name__ == '__main__':
    main()
