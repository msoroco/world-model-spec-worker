"""Bind six exact offline sweep construction receipts to canonical points."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'sweep-cases'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    stage = json.loads((HERE / 'proposals/cases.json').read_text())
    canonical = {c['case_id']: c for c in stage['cases']
                 if c['target_type'] == 'judgment_sweep'}
    index = json.loads((OUT / 'index.json').read_text())
    manifest = json.loads((OUT / 'manifest.json').read_text())
    if len(canonical) != 6 or len(index['entries']) != 6 or len(manifest['cases']) != 6:
        raise ValueError('Incomplete canonical physical sweep matrix')
    if index['semantic_index_sha256'] != sha(HERE / 'proposals/semantic-index.json'):
        raise ValueError('Canonical semantic stage changed')
    receipts = []
    for entry in index['entries']:
        case_id = entry['case_id']
        case = canonical[case_id]
        construction_path = HERE / entry['construction']
        if sha(construction_path) != entry['construction_sha256']:
            raise ValueError('Construction hash changed')
        construction = json.loads(construction_path.read_text())
        if construction['case_id'] != case_id or construction['recording_description'] != case['recording_description']:
            raise ValueError('Construction identity or recording contract differs')
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        point = next(iter(case['sweep_point'].values()))
        if config['case_id'] != case_id or config['sweep_target'] != point:
            raise ValueError('Frozen sweep target differs')
        if config['duration_s'] != 30 or config['rate_hz'] != 20 or len(config['cameras']) != 4:
            raise ValueError('Original capture contract differs')
        scratch = ROOT / '.runtime-work/c229597-sweep-offline-v4' / case_id
        log_source = scratch / 'offline.log'
        if not log_source.exists() or 'OK' not in log_source.read_text():
            raise ValueError('Pinned exact offline test missing: ' + case_id)
        saved_log = construction_path.parent / 'offline.log'
        if not saved_log.is_file() or '"simulation_started": false' not in saved_log.read_text():
            raise ValueError('Permanent exact offline command receipt missing: ' + case_id)
        receipts.append({'case_id': case_id,
                         'construction_sha256': sha(construction_path),
                         'offline_log': str(saved_log.relative_to(HERE)),
                         'offline_log_sha256': sha(saved_log),
                         'source_target': point,
                         'physical_response_verified': False})
    proof = {'format': 'c229597-canonical-sweep-offline-proof-v1',
             'semantic_index_sha256': index['semantic_index_sha256'],
             'manifest_sha256': sha(OUT / 'manifest.json'),
             'cases': receipts, 'selected': True,
             'synthetic_planning_bounds_only': True,
             'native_executed': False, 'physical_acceptance_claimed': False,
             'highway_status_verified': False, 'legal_verdict_claimed': False}
    path = OUT / 'exact-cpu-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': len(receipts), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
