"""Exercise selected Walk receipt and controlled-comparison rejection paths."""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('selected_pair', HERE / 'audit-selected-cpu-pair.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = module.read(HERE / 'execution-manifest.json')
matrix = module.read(HERE / 'update020-selected-process-saved-matrix.json')
positive = module.audit(manifest, matrix)
assert positive['selected_cases'] == 2 and positive['candidate_receipts_verified'] == 8
rejected = []
for name in ('missing_fallback', 'wrong_construction_hash', 'missing_saved_receipt',
             'wrong_manifest_binding', 'wrong_compatibility_receipt',
             'wrong_physical_receipt'):
    edited_manifest = copy.deepcopy(manifest)
    edited_matrix = copy.deepcopy(matrix)
    if name == 'missing_fallback':
        edited_manifest['cases'][0]['candidates'].pop()
    elif name == 'wrong_construction_hash':
        edited_manifest['cases'][0]['construction_sha256'] = '0' * 64
    elif name == 'missing_saved_receipt':
        edited_matrix['rows'].pop()
    elif name == 'wrong_manifest_binding':
        edited_matrix['manifest_sha256'] = '0' * 64
    elif name == 'wrong_compatibility_receipt':
        edited_manifest['cases'][0]['compatibility']['sha256'] = '0' * 64
    else:
        edited_manifest['cases'][0]['physical_preparation']['sha256'] = '0' * 64
    try:
        module.audit(edited_manifest, edited_matrix)
    except (ValueError, KeyError, StopIteration):
        rejected.append(name)
    else:
        raise ValueError('Selected pair audit accepted ' + name)
print(json.dumps({'format': 'c111256-selected-cpu-pair-proof-v1',
                  'positive_verified': True, 'negative_rejections': rejected,
                  'original_physical_acceptance_claimed': False}, sort_keys=True))
