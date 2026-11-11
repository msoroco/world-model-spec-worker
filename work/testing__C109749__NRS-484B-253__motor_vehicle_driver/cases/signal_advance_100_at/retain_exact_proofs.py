"""Retain source-bound exact diagnostic compatibility and saved receipts."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
repo = assignment.parent.parent
case = assignment.name + '__signal_advance_100_at'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def retain(stage):
    stage = Path(stage).resolve()
    manifest_path = stage / 'work' / assignment.name / 'draft-manifest.json'
    staged = read(manifest_path)['cases'][0]
    current = read(folder / 'draft-manifest.json')['cases'][0]
    if staged['case_id'] != case or staged['construction_sha256'] != current['construction_sha256']:
        raise ValueError('Stage does not bind current exact case construction')
    recipe_hash = sha(folder / 'diagnostic-recipe.json')
    contract_hash = sha(folder / 'measurement-contract.json')
    staged_recipe = stage / 'work' / assignment.name / 'cases/signal_advance_100_at/diagnostic-recipe.json'
    staged_contract = stage / 'work' / assignment.name / 'cases/signal_advance_100_at/measurement-contract.json'
    if sha(staged_recipe) != recipe_hash or sha(staged_contract) != contract_hash:
        raise ValueError('Stage source recipe or measurement contract changed')
    out = folder / 'proofs'
    out.mkdir(exist_ok=True)
    proofs = []
    for label, entry in [('primary', current),
                         *[(x['id'], x) for x in current['candidates']]]:
        if sha(folder / entry['construction']) != entry['construction_sha256']:
            raise ValueError('Current candidate construction changed: ' + label)
        attempt = stage / '.runtime-work' / ('signal-advance-' + label + '-compat')
        version = stage / '.runtime-work' / ('signal-advance-' + label + '-saved/v0001')
        compatibility = read(attempt / 'compatibility.json')
        processing = read(version / 'processing.json')
        result = read(attempt / 'result.json')
        saved_result = read(version / 'analysis/result.json')
        for name, value in [('compatibility', compatibility), ('saved', processing)]:
            if value.get('case_id') != case or value.get('candidate_id') != label or value.get('passed') is not True:
                raise ValueError(name + ' is not current positive proof: ' + label)
        if (compatibility['construction_sha256'] != entry['construction_sha256'] or
                compatibility['measurement_contract_sha256'] != contract_hash or
                compatibility['fixture_recipe_sha256'] != recipe_hash or
                'negative_case_source' not in compatibility['checks']):
            raise ValueError('Compatibility source binding incomplete: ' + label)
        if (processing.get('recorded_only') is not True or
                processing.get('missing_evidence') is not False or
                processing.get('originals_preserved') is not True or
                processing.get('timestamp_joins', {}).get('frames') != 210 or
                processing.get('timestamp_joins', {}).get('passed') is not True):
            raise ValueError('Saved source processing incomplete: ' + label)
        for measured in (result, saved_result):
            distance = measured['measured_values']['observed_continuous_signal_advance_m']
            target = next(x for x in measured['target_checks']
                          if x['target'] == 'continuous_left_signal_at_least_30_48_m')
            if not 30.48 <= distance < 30.480001 or target['matched'] is not True:
                raise ValueError('Diagnostic target measurement missing: ' + label)
        target = out / label
        target.mkdir(exist_ok=True)
        artifacts = {
            'compatibility.json': attempt / 'compatibility.json',
            'negative-analysis.log': attempt / 'negative-analysis.log',
            'compatibility-analysis.log': attempt / 'compatibility-analysis.log',
            'processing.json': version / 'processing.json',
            'saved-analysis.log': version / 'analysis.log',
            'compatibility-command.log': stage / (label + '-compatibility.log'),
            'saved-command.log': stage / (label + '-saved.log'),
        }
        for name, source in artifacts.items():
            shutil.copyfile(source, target / name)
        proofs.append({'candidate_id': label,
                       'construction_sha256': entry['construction_sha256'],
                       'compatibility': {'passed': True,
                                         'receipt': str((target / 'compatibility.json').relative_to(folder)),
                                         'sha256': sha(target / 'compatibility.json'),
                                         'negative_log_sha256': sha(target / 'negative-analysis.log'),
                                         'command_log_sha256': sha(target / 'compatibility-command.log')},
                       'saved': {'passed': True, 'recorded_only': True,
                                 'receipt': str((target / 'processing.json').relative_to(folder)),
                                 'sha256': sha(target / 'processing.json'),
                                 'command_log_sha256': sha(target / 'saved-command.log')},
                       'diagnostic_frames': 210,
                       'physical_acceptance_claimed': False})
    receipt = {'format': 'worker-signal-advance-exact-diagnostic-proofs',
               'case_id': case, 'canonical_selected': False,
               'fixture_recipe_sha256': recipe_hash,
               'diagnostic_sha256': sha(folder / 'diagnostic.json'),
               'measurement_contract_sha256': contract_hash,
               'stage_manifest_sha256': sha(manifest_path),
               'source_kind': 'synthetic_fixture',
               'physical_acceptance_claimed': False,
               'legal_acceptance_claimed': False,
               'proofs': proofs}
    (folder / 'exact-proof-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'candidates': len(proofs),
                      'positive_compatibility': 4, 'negative_source_checks': 4,
                      'recorded_only_saved': 4, 'canonical_selected': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    retain(parser.parse_args().stage)
