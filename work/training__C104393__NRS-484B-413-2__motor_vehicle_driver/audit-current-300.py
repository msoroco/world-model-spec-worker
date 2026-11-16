"""Independently bind the current four-candidate diagnostic proof."""
import hashlib
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feet', type=int, default=300)
    feet = parser.parse_args().feet
    summary = json.loads((HERE/f'current-v2-{feet}-summary.json').read_text())
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == summary['case_id'])
    seen = set(); maps = {}
    for item in summary['candidate_receipts']:
        candidate = item['candidate_id']
        if candidate in seen or sha(HERE/item['receipt']) != item['sha256']:
            raise ValueError('Duplicate or changed candidate receipt')
        seen.add(candidate)
        proof = json.loads((HERE/item['receipt']).read_text())
        ref = entry if candidate == 'primary' else next(r for r in entry['candidates'] if r['id']==candidate)
        if sha(HERE/ref['construction']) != ref['construction_sha256'] or \
           proof['construction_sha256'] != ref['construction_sha256'] or \
           proof['case_id'] != entry['case_id'] or proof['candidate_id'] != candidate or \
           proof['fixture_recipe_sha256'] != sha(HERE/item['recipe']) or \
           proof['measurement_contract_sha256'] != sha(HERE/entry['measurement_contract']):
            raise ValueError('Exact construction, recipe or contract differs')
        if not {'selected_measurements','negative_case_source','four_camera_sources',
                'derived_outputs_rebuilt','lean_decoder','final_decode'} <= set(proof['checks']):
            raise ValueError('Current runtime checks incomplete')
        if proof['log_sha256'] != sha(HERE/item['analysis_log']) or \
           proof['negative_log_sha256'] != sha(HERE/item['negative_log']) or \
           proof['negative_error_contains'] not in (HERE/item['negative_log']).read_text():
            raise ValueError('Positive or negative log changed')
        actual = proof['measurement_examples']['continuous_signal_distance_ft']['value']
        if abs(actual-feet)>0.5:
            raise ValueError('Measured signal distance outside requested fixture')
        construction = json.loads((HERE/ref['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        maps[candidate] = config['native_request']['map_sha256']
    if seen != {'primary','fallback1','fallback2','fallback3'} or \
       maps['fallback1'] == maps['primary'] or \
       maps['fallback2'] != maps['primary'] or maps['fallback3'] != maps['primary']:
        raise ValueError('Fallback map separation or cardinality differs')
    print(json.dumps({'passed':True,'strict_recipe_candidates':4,
                      'geometry_specific_recipe':'fallback1',
                      'scope':'unselected synthetic; no physical or legal acceptance'}))


if __name__ == '__main__':
    main()
