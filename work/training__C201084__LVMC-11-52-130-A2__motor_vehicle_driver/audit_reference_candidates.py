"""Independently inspect four exact synthetic reference candidate proof chains."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest_path = HERE/'draft-reference-fallback-manifest.json'
    manifest = read(manifest_path)
    entry = manifest['cases'][0]
    contract = read(HERE/entry['measurement_contract'])
    contract_keys = sorted(row['output_key'] for row in contract['requirements'])
    constructions = {'primary': {'construction': entry['construction'],
                                 'construction_sha256': entry['construction_sha256']}}
    constructions.update({row['id']: row for row in entry['candidates']})
    if set(constructions) != set(NAMES) or len({row['construction_sha256']
                                                for row in constructions.values()}) != 4:
        raise ValueError('Four distinct construction candidates required')
    audited = {}
    for name in NAMES:
        selected = constructions[name]
        if sha(HERE/selected['construction']) != selected['construction_sha256']:
            raise ValueError('Construction hash differs: '+name)
        construction = read(HERE/selected['construction'])
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        if config['candidate_id'] != name or config['frames'] != 600 or \
                config['rate_hz'] != 20 or config['duration_s'] != 30:
            raise ValueError('Candidate identity or clock differs: '+name)
        receipt = read(HERE/('update103-'+name+'-compatibility-receipt.json'))
        saved = read(HERE/('update103-'+name+'-saved-receipt.json'))
        if receipt['passed'] is not True or receipt['candidate_id'] != name or \
                receipt['construction_sha256'] != selected['construction_sha256'] or \
                receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or \
                receipt['measurement_contract_sha256'] != sha(HERE/entry['measurement_contract']) or \
                sorted(receipt['measurement_keys']) != contract_keys:
            raise ValueError('Compatibility selection or measurement differs: '+name)
        if not {'actual_analysis', 'acquisition_unchanged', 'native_validation',
                'mandatory_observations', 'four_camera_sources', 'lean_decoder',
                'render', 'final_decode', 'selected_measurements',
                'negative_case_source'} <= set(receipt['checks']):
            raise ValueError('Compatibility checks incomplete: '+name)
        negative = (HERE/('update103-'+name+'-negative-analysis.log')).read_text()
        if receipt['negative_removed'] != contract['negative']['remove'][0] or \
                contract['negative']['error_contains'] not in negative or \
                receipt['negative_log_sha256'] != sha(HERE/('update103-'+name+'-negative-analysis.log')):
            raise ValueError('Missing-source negative differs: '+name)
        if receipt['log_sha256'] != sha(HERE/('update103-'+name+'-compatibility-analysis.log')):
            raise ValueError('Compatibility analyzer log differs: '+name)
        offline = read(Path('.runtime-work')/('c201084-update103-'+name+'-offline-2')/'candidate-selection.json')
        if offline['candidate_id'] != name or offline['construction_sha256'] != \
                selected['construction_sha256'] or offline['manifest_sha256'] != sha(manifest_path):
            raise ValueError('Offline selection differs: '+name)
        attempt = ROOT/'.runtime-work'/('c201084-update103-'+name+'-compatibility')
        if saved['passed'] is not True or saved['recorded_only'] is not True or \
                saved['candidate_id'] != name or saved['missing_evidence'] is not False or \
                saved['originals_preserved'] is not True or \
                saved['timestamp_joins']['frames'] != 600 or \
                saved['timestamp_joins']['passed'] is not True or \
                saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']:
            raise ValueError('Saved process incomplete or acceptance claimed: '+name)
        for relative, checksum in saved['original_source_hashes'].items():
            if sha(attempt/relative) != checksum:
                raise ValueError('Original source changed: '+name+'/'+relative)
        result = read(ROOT/'.runtime-work'/('c201084-update103-'+name+'-saved')/
                      'v0001/analysis/result.json')
        if result['provenance_kind'] != 'synthetic_fixture' or \
                result['diagnostic_fixture'] is not True or result['accepted'] or \
                result['physical_acceptance_claimed'] or result['legal_verdict_claimed']:
            raise ValueError('Synthetic result claimed acceptance: '+name)
        audited[name] = {'construction_sha256': selected['construction_sha256'],
                         'offline_selection_sha256': sha(Path('.runtime-work')/
                             ('c201084-update103-'+name+'-offline-2')/'candidate-selection.json'),
                         'compatibility_receipt_sha256': sha(HERE/('update103-'+name+'-compatibility-receipt.json')),
                         'saved_receipt_sha256': sha(HERE/('update103-'+name+'-saved-receipt.json')),
                         'source_count': len(saved['original_source_hashes'])}
    return {'format': 'c201084-reference-candidate-matrix-audit',
            'passed': True, 'case_id': entry['case_id'],
            'manifest_sha256': sha(manifest_path), 'candidates': audited,
            'synthetic_only': True, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    output = audit()
    (HERE/'update103-reference-candidate-audit.json').write_text(
        json.dumps(output, indent=2, sort_keys=True)+'\n')
    print(json.dumps(output, sort_keys=True))
