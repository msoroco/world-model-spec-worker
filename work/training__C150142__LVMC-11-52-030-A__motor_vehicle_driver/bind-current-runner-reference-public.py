"""Retain current-runner reference public compatibility proofs in a draft."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUNNER_SOURCE = ROOT / 'current-runtime-runner-offline-bound-manifest.json'
DELIVERY_SOURCE = ROOT / 'current-delivery-bound-draft-manifest.json'
CASE = ROOT.name + '__reference'
TARGET = ROOT / 'current-runtime-runner-reference-bound-manifest.json'
PORTABLE = ROOT / 'current-runtime-runner-public/reference'
TMP = REPO / '.runtime-work/owner150142/public-binding-tmp'
VARIANTS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retain(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha(source) != sha(destination):
            raise ValueError('Current public receipt changed: ' + str(destination))
        return
    TMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=TMP, delete=False) as stream:
        stream.write(source.read_bytes())
        temporary = Path(stream.name)
    os.replace(temporary, destination)


def run():
    manifest = json.loads(DELIVERY_SOURCE.read_text(encoding='utf-8'))
    runner = json.loads(RUNNER_SOURCE.read_text(encoding='utf-8'))
    if [entry['case_id'] for entry in manifest['cases']] != [entry['case_id'] for entry in runner['cases']]:
        raise ValueError('Current runner and delivery case inventories differ')
    for delivery_entry, runner_entry in zip(manifest['cases'], runner['cases']):
        for field in ('construction', 'construction_sha256', 'offline'):
            delivery_entry[field] = runner_entry[field]
        delivery_candidates = delivery_entry['candidates']
        runner_candidates = runner_entry['candidates']
        if [item['id'] for item in delivery_candidates] != [item['id'] for item in runner_candidates]:
            raise ValueError('Current runner and delivery candidate inventories differ')
        for delivery_candidate, runner_candidate in zip(delivery_candidates, runner_candidates):
            for field in ('construction', 'construction_sha256', 'offline'):
                delivery_candidate[field] = runner_candidate[field]
    matches = [entry for entry in manifest['cases'] if entry['case_id'] == CASE]
    if len(matches) != 1:
        raise ValueError('Reference case missing or duplicated')
    entry = matches[0]
    fields = {'primary': entry, **{item['id']: item for item in entry['candidates']}}
    completed = []
    for variant in VARIANTS:
        scratch = REPO / ('.runtime-work/owner150142/current-runner-reference-'
                          + variant + '-public-v1')
        receipt_path = scratch / 'compatibility.json'
        if not receipt_path.is_file():
            continue
        field = fields[variant]
        proof = json.loads(receipt_path.read_text(encoding='utf-8'))
        if (proof.get('case_id') != CASE or proof.get('candidate_id') != variant or
                proof.get('construction_sha256') != field['construction_sha256'] or
                proof.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256'] or
                proof.get('passed') is not True or
                not {'selected_measurements', 'negative_case_source', 'lean_decoder',
                     'final_decode'} <= set(proof.get('checks', []))):
            raise ValueError('Public proof does not bind current reference ' + variant)
        sources = {'compatibility.json': receipt_path,
                   'compatibility-analysis.log': scratch / 'compatibility-analysis.log',
                   'negative-analysis.log': scratch / 'negative-analysis.log'}
        if (sha(sources['compatibility-analysis.log']) != proof['log_sha256'] or
                sha(sources['negative-analysis.log']) != proof['negative_log_sha256'] or
                proof['negative_error_contains'] not in sources['negative-analysis.log'].read_text()):
            raise ValueError('Public positive or source-negative log changed: ' + variant)
        portable = PORTABLE / variant
        portable_names = {'compatibility.json': 'compatibility.json',
                          'compatibility-analysis.log': 'positive-analysis.log',
                          'negative-analysis.log': 'negative-analysis.log'}
        for name, source in sources.items():
            retain(source, portable / portable_names[name])
        field['compatibility'] = {
            'receipt': str((portable / 'compatibility.json').relative_to(ROOT)),
            'sha256': sha(portable / 'compatibility.json'),
            'log': str((portable / 'positive-analysis.log').relative_to(ROOT)),
            'negative_log': str((portable / 'negative-analysis.log').relative_to(ROOT)),
        }
        field['negative'] = {
            'log': str((portable / 'negative-analysis.log').relative_to(ROOT)),
        }
        completed.append({'candidate_id': variant,
                          'construction_sha256': field['construction_sha256'],
                          'positive_log_sha256': proof['log_sha256'],
                          'negative_log_sha256': proof['negative_log_sha256']})
    if not completed:
        raise ValueError('No current reference public proof available')
    manifest['status'] = 'draft_current_runner_reference_public_bound'
    manifest['delivery_ready'] = False
    TMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=TMP,
                                     delete=False) as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, TARGET)
    return {'case_id': CASE, 'completed': completed,
            'bound_manifest_sha256': sha(TARGET), 'passed': True,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
