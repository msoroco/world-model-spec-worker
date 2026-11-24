"""Bind returned current-runtime diagnostic receipts to exact candidate sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('controlled_1', 'controlled_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def bind():
    manifest = read(HERE / 'current-probe-manifest.json')
    selected = {entry['case_id']: entry for entry in manifest['cases']}
    public_rows, saved_rows = [], []
    for suffix in CASES:
        case_id = HERE.name + '__' + suffix
        entry = selected[case_id]
        recipe = HERE / ('current-' + suffix + '-recipe.json')
        contract = HERE / entry['measurement_contract']
        for candidate in CANDIDATES:
            name = suffix + '-' + candidate
            chosen = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            construction_hash = chosen['construction_sha256']
            base = HERE / 'current-public'
            receipt_path = base / (name + '-receipt.json')
            analysis_path = base / (name + '-analysis.log')
            negative_path = base / (name + '-negative.log')
            receipt = read(receipt_path)
            if (receipt['passed'] is not True or receipt['case_id'] != case_id
                    or receipt['candidate_id'] != candidate
                    or receipt['construction_sha256'] != construction_hash
                    or receipt['fixture_recipe_sha256'] != sha(recipe)
                    or receipt['measurement_contract_sha256'] != sha(contract)
                    or receipt['log_sha256'] != sha(analysis_path)
                    or receipt['negative_log_sha256'] != sha(negative_path)
                    or 'negative_case_source' not in receipt['checks']
                    or 'final_decode' not in receipt['checks']):
                raise ValueError('Public receipt differs: ' + name)
            public_rows.append({'case_id': case_id, 'candidate_id': candidate,
                                'construction_sha256': construction_hash,
                                'receipt': receipt_path.relative_to(HERE).as_posix(),
                                'sha256': sha(receipt_path),
                                'analysis_log_sha256': sha(analysis_path),
                                'negative_log_sha256': sha(negative_path),
                                'passed': True})
            saved_base = HERE / 'current-saved'
            saved_path = saved_base / (name + '-receipt.json')
            saved_log = saved_base / (name + '-analysis.log')
            saved = read(saved_path)
            if (saved['passed'] is not True or saved['recorded_only'] is not True
                    or saved['originals_preserved'] is not True
                    or saved['case_id'] != case_id
                    or saved['candidate_id'] != candidate
                    or saved['native_revision']['construction_sha256'] != construction_hash
                    or saved['analysis_revision']['construction_sha256'] != construction_hash
                    or saved['analysis_log_sha256'] != sha(saved_log)
                    or saved['timestamp_joins']['passed'] is not True
                    or saved['legal_acceptance_claimed'] is not False
                    or saved['physical_acceptance_claimed'] is not False):
                raise ValueError('Saved receipt differs: ' + name)
            saved_rows.append({'case_id': case_id, 'candidate_id': candidate,
                               'construction_sha256': construction_hash,
                               'receipt': saved_path.relative_to(HERE).as_posix(),
                               'sha256': sha(saved_path),
                               'analysis_log_sha256': sha(saved_log),
                               'passed': True, 'recorded_only': True})
    for name, rows in [('public', public_rows), ('saved', saved_rows)]:
        path = HERE / 'current' / (name + '-matrix.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'format': 'c404492-current-' + name + '-matrix',
                                    'status': 'diagnostic_only', 'all_passed': True,
                                    'results': rows}, indent=2) + '\n')
        print(name, len(rows), sha(path))


if __name__ == '__main__':
    bind()
