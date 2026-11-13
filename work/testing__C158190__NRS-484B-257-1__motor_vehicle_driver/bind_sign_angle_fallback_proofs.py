"""Return exact sign-angle fallback offline and positive/negative CPU receipts."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate

MANIFEST = ROOT / 'sign-angle-compatibility-manifest.json'
SOURCE_MANIFEST = ROOT / 'sign-angle-fallback1-source-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads(MANIFEST.read_text())
    source_manifest = json.loads(SOURCE_MANIFEST.read_text())
    source_entries = {entry['case_id']: entry for entry in source_manifest['cases']}
    proofs = []
    for entry in manifest['cases']:
        label = entry['case_id'].split('sign_angle_')[1]
        require(entry['case_id'] in source_entries, 'Fallback source case missing')
        for candidate in entry['candidates']:
            ident = candidate['id']
            construction = ROOT / candidate['construction']
            require(sha(construction) == candidate['construction_sha256'],
                    'Fallback construction changed')
            folder = ROOT / f'cases/sign_angle_{label}/fallbacks'
            offline_log = folder / f'{ident}-offline.log'
            offline_receipt = json.loads(offline_log.read_text())
            native_offline_log = REPO / f'.runtime-work/c158190-sign-angle-{label}-{ident}-offline-v1/offline.log'
            require(offline_receipt.get('offline_passed') is True
                    and offline_receipt.get('case_id') == entry['case_id']
                    and offline_receipt.get('candidate_id') == ident
                    and native_offline_log.is_file() and 'OK' in native_offline_log.read_text(),
                    'Returned offline tests missing or failed')
            candidate['offline'] = {
                'exit_code': 0,
                'construction_sha256': candidate['construction_sha256'],
                'command': ('.venv-cpu/bin/python runtime.py offline --manifest '
                            + str(MANIFEST.relative_to(REPO)) + ' --case '
                            + entry['case_id'] + ' --candidate ' + ident + ' --output '
                            + f'.runtime-work/c158190-sign-angle-{label}-{ident}-offline-v1'),
                'log': str(offline_log.relative_to(ROOT)),
                'log_sha256': sha(offline_log),
            }
            if ident == 'fallback1':
                fixture_recipe = source_entries[entry['case_id']]['fixture_recipe']
                compatibility_manifest = SOURCE_MANIFEST
                suffix = '-source-compat-v1'
                saved_suffix = '-source-saved-v1'
            else:
                fixture_recipe = entry['fixture_recipe']
                compatibility_manifest = MANIFEST
                suffix = '-compat-v1'
                saved_suffix = '-saved-v1'
            source = REPO / f'.runtime-work/c158190-sign-angle-{label}-{ident}{suffix}'
            receipt = json.loads((source / 'compatibility.json').read_text())
            require(receipt.get('format') == 'worker-package-compatibility'
                    and receipt.get('passed') is True
                    and receipt.get('case_id') == entry['case_id']
                    and receipt.get('candidate_id') == ident
                    and receipt.get('construction_sha256') == candidate['construction_sha256']
                    and receipt.get('fixture_recipe_sha256') == sha(REPO / fixture_recipe)
                    and receipt.get('negative_removed') == 'visibility_rays.jsonl'
                    and {'selected_measurements', 'negative_case_source',
                         'lean_decoder', 'final_decode'} <= set(receipt.get('checks', [])),
                    'Fallback compatibility receipt differs')
            returned = {}
            for name, source_name in (('receipt', 'compatibility.json'),
                                      ('log', 'compatibility-analysis.log'),
                                      ('negative_log', 'negative-analysis.log')):
                target = folder / f'{ident}-{source_name}'
                shutil.copyfile(source / source_name, target)
                returned[name] = str(target.relative_to(ROOT))
            require(sha(ROOT / returned['log']) == receipt['log_sha256']
                    and sha(ROOT / returned['negative_log']) == receipt['negative_log_sha256'],
                    'Returned positive or negative log changed')
            candidate['compatibility'] = {
                'receipt': returned['receipt'],
                'sha256': sha(ROOT / returned['receipt']),
                'log': returned['log'],
                'negative_log': returned['negative_log'],
            }
            candidate['fixture_recipe'] = fixture_recipe
            candidate['compatibility_manifest'] = str(compatibility_manifest.relative_to(REPO))
            processing = REPO / (f'.runtime-work/c158190-sign-angle-{label}-{ident}'
                                 + saved_suffix + '/v0001/processing.json')
            saved = json.loads(processing.read_text())
            require(saved.get('passed') is True
                    and saved.get('candidate_id') == ident
                    and saved.get('recorded_only') is True
                    and saved.get('originals_preserved') is True,
                    'Exact fallback saved-processing receipt missing')
            candidate['saved_processing_sha256'] = sha(processing)
            proofs.append({'case_id': entry['case_id'], 'candidate_id': ident,
                           'construction_sha256': candidate['construction_sha256'],
                           'fixture_recipe_sha256': sha(REPO / fixture_recipe),
                           'compatibility_receipt_sha256': candidate['compatibility']['sha256'],
                           'saved_processing_sha256': candidate['saved_processing_sha256']})
        validate(ROOT, entry, 'NRS-484B-257-1', 'C158190',
                 required=True, require_alternate=True, candidate_count=4)
    require(len(proofs) == 9, 'Nine returned fallback proofs required')
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'format': 'c158190-sign-angle-fallback-returned-proofs',
                      'cases': len(manifest['cases']), 'fallbacks': proofs,
                      'required_candidate_validation_passed': True,
                      'physical_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
