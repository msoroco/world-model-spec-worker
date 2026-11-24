"""Check exact eight unselected current-v2 diagnostic and saved receipts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = read(FOLDER / 'draft-execution-manifest.json')
    assert manifest['status'] == 'draft_not_selected'
    rows = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        case = case_id.rsplit('__', 1)[1]
        recipe = FOLDER.parents[1] / entry['fixture_recipe']
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            name = ('current-v2' if case == 'controlled_1' else 'controlled2-primary') if candidate == 'primary' else case + '-' + candidate
            compatibility = FOLDER / ('owner194-' + name + '-compatibility.json')
            saved = FOLDER / ('owner194-' + name + '-saved-processing.json')
            a, b = read(compatibility), read(saved)
            selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
            assert a['passed'] is True and a['case_id'] == b['case_id'] == case_id
            assert a['candidate_id'] == b['candidate_id'] == candidate
            assert a['construction_sha256'] == selected['construction_sha256']
            assert a['fixture_recipe_sha256'] == sha(recipe)
            assert {'actual_analysis', 'native_validation', 'selected_measurements', 'negative_case_source',
                    'four_camera_sources', 'lean_decoder', 'final_decode', 'acquisition_unchanged',
                    'derived_outputs_rebuilt'} <= set(a['checks'])
            assert a['negative_removed'] == 'road_geometry.json'
            assert b['passed'] is True and b['recorded_only'] is True and b['originals_preserved'] is True
            assert b['timestamp_joins']['passed'] is True and b['timestamp_joins']['frames'] == 600
            assert b['physical_acceptance_claimed'] is False and b['legal_acceptance_claimed'] is False
            rows.append({'case_id': case_id, 'candidate': candidate,
                         'compatibility_sha256': sha(compatibility), 'saved_sha256': sha(saved),
                         'construction_sha256': selected['construction_sha256']})
    proof = {'format': 'c110919-current-v2-unselected-matrix-audit',
             'manifest_sha256': sha(FOLDER / 'draft-execution-manifest.json'),
             'cases': 2, 'candidates': 8, 'compatibility_passed': 8,
             'recorded_only_saved_passed': 8, 'selected': False,
             'physical_acceptance_claimed': False, 'rows': rows}
    (FOLDER / 'owner194-current-v2-matrix-audit.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(rows),
                      'proof_sha256': sha(FOLDER / 'owner194-current-v2-matrix-audit.json')}))

if __name__ == '__main__':
    main()
