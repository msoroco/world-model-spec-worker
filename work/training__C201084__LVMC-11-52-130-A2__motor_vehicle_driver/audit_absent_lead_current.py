"""Independently audit current-runtime diagnostic absent_lead candidate chains."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
REQUIRED = {'actual_analysis', 'acquisition_unchanged', 'native_validation',
            'mandatory_observations', 'four_camera_sources', 'lean_decoder',
            'render', 'final_decode', 'selected_measurements',
            'negative_case_source', 'derived_outputs_rebuilt'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest_path = HERE/'draft-absent_lead-fallback-manifest.json'
    manifest = read(manifest_path)
    entry = manifest['cases'][0]
    require(manifest['runtime_manifest_sha256'] ==
            sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Absent Lead manifest binds another runtime')
    selected = {'primary': {'construction': entry['construction'],
                            'construction_sha256': entry['construction_sha256']}}
    selected.update({row['id']: row for row in entry['candidates']})
    require(set(selected) == set(NAMES) and
            len({row['construction_sha256'] for row in selected.values()}) == 4,
            'Four distinct constructions required')
    contract = read(HERE/entry['measurement_contract'])
    keys = sorted(row['output_key'] for row in contract['requirements'])
    audited = {}
    for name in NAMES:
        base = ROOT/'.runtime-work'/('c201084-absent_lead-current-'+name)
        returned = HERE/('current-absent_lead-'+name)
        offline_path = Path(str(returned)+'-offline-selection.json')
        compatibility_path = Path(str(returned)+'-compatibility-receipt.json')
        saved_path = Path(str(returned)+'-saved-receipt.json')
        negative_path = Path(str(returned)+'-negative-analysis.log')
        analysis_log_path = Path(str(returned)+'-compatibility-analysis.log')
        offline = read(offline_path)
        attempt = Path(str(base)+'-compatibility')
        compatibility = read(compatibility_path)
        saved = read(saved_path)
        require(sha(offline_path) == sha(Path(str(base)+'-offline')/'candidate-selection.json') and
                sha(compatibility_path) == sha(attempt/'compatibility.json') and
                sha(saved_path) == sha(Path(str(base)+'-saved')/'v0001/processing.json'),
                name+': returned receipt differs from generated proof')
        construction_path = HERE/selected[name]['construction']
        require(sha(construction_path) == selected[name]['construction_sha256'],
                name+': construction hash differs')
        construction = read(construction_path)
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        require(config['candidate_id'] == name and config['frames'] == 600 and
                config['rate_hz'] == 20 and config['duration_s'] == 30,
                name+': candidate identity or clock differs')
        require(offline['candidate_id'] == name and
                offline['construction_sha256'] == selected[name]['construction_sha256'] and
                offline['manifest_sha256'] == sha(manifest_path),
                name+': offline binding differs')
        require(compatibility['passed'] is True and
                compatibility['candidate_id'] == name and
                compatibility['construction_sha256'] == selected[name]['construction_sha256'] and
                compatibility['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'] and
                compatibility['measurement_contract_sha256'] ==
                sha(HERE/entry['measurement_contract']) and
                sorted(compatibility['measurement_keys']) == keys and
                REQUIRED <= set(compatibility['checks']),
                name+': compatibility proof incomplete')
        negative = negative_path
        require(compatibility['negative_removed'] == contract['negative']['remove'][0] and
                contract['negative']['error_contains'] in negative.read_text() and
                compatibility['negative_log_sha256'] == sha(negative) and
                compatibility['log_sha256'] == sha(analysis_log_path) and
                sha(negative_path) == sha(attempt/'negative-analysis.log'),
                name+': negative source rejection differs')
        require(saved['passed'] is True and saved['recorded_only'] is True and
                saved['candidate_id'] == name and
                saved['missing_evidence'] is False and
                saved['originals_preserved'] is True and
                saved['timestamp_joins']['passed'] is True and
                saved['timestamp_joins']['frames'] == 600 and
                saved['physical_acceptance_claimed'] is False and
                saved['legal_acceptance_claimed'] is False,
                name+': saved process incomplete or acceptance claimed')
        for path, checksum in saved['original_source_hashes'].items():
            require(sha(attempt/path) == checksum,
                    name+': original changed: '+path)
        result = read(Path(str(base)+'-saved')/'v0001/analysis/result.json')
        require(result['provenance_kind'] == 'synthetic_fixture' and
                result['diagnostic_fixture'] is True and
                result['accepted'] is False and
                result['physical_acceptance_claimed'] is False and
                result['legal_verdict_claimed'] is False,
                name+': synthetic result claimed acceptance')
        audited[name] = {
            'construction_sha256': selected[name]['construction_sha256'],
            'offline_selection_sha256': sha(offline_path),
            'compatibility_receipt_sha256': sha(compatibility_path),
            'saved_receipt_sha256': sha(saved_path),
            'source_count': len(saved['original_source_hashes'])}
    return {'format': 'c201084-current-absent_lead-candidate-audit',
            'passed': True, 'case_id': entry['case_id'],
            'manifest_sha256': sha(manifest_path),
            'candidates': audited, 'synthetic_only': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    output = audit()
    (HERE/'current-absent_lead-candidate-audit.json').write_text(
        json.dumps(output, indent=2, sort_keys=True)+'\n')
    print(json.dumps(output, sort_keys=True))
