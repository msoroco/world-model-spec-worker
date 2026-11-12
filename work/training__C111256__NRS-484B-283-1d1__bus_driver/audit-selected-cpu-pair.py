"""Independent source and receipt check for the selected diagnostic Walk pair."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SOURCES = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json')
VARIABLE_KEYS = {'case_id', 'case_suffix', 'selected_case_id', 'supported_case_ids', 'case'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def audit(manifest, matrix):
    require(manifest['format'] == 'worker-execution-manifest' and
            manifest['assignment_id'] == AID and
            {entry['case_id'].removeprefix(AID + '__') for entry in manifest['cases']} ==
            {'reference', 'contrast'}, 'Selected Walk pair differs')
    require(matrix['format'] == 'c111256-selected-process-saved-matrix-v1' and
            matrix['manifest_sha256'] == sha(HERE / 'execution-manifest.json') and
            len(matrix['rows']) == 8, 'Selected saved proof matrix differs')
    receipts = {(row['case_id'], row['candidate_id']): row for row in matrix['rows']}
    require(len(receipts) == 8, 'Duplicate selected saved receipt')
    pairs = {}
    configs = {}
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(AID + '__')
        require(entry['kind'] == 'delivery' and
                entry['candidate_risk']['status'] == 'physical' and
                len(entry['candidates']) == 3, 'Selected physical alternatives differ')
        physical_ref = entry.get('physical_preparation', {})
        physical_path = HERE / physical_ref.get('receipt', '')
        require(physical_path.is_file() and sha(physical_path) == physical_ref.get('sha256'),
                'Selected physical fixture receipt differs')
        physical = read(physical_path)
        require(physical.get('fixtures_are_cpu_mocks') is True and
                physical.get('original_native_motion_verified') is False and
                physical.get('original_walk_pixels_verified') is False and
                physical.get('construction_sha256') == entry['construction_sha256'],
                'Physical CPU mock was promoted to original')
        for candidate_id in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            candidate = entry if candidate_id == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate_id)
            construction = HERE / candidate['construction']
            require(sha(construction) == candidate['construction_sha256'],
                    'Selected construction hash changed')
            proof = candidate['compatibility']
            receipt_path = HERE / proof['receipt']
            receipt = read(receipt_path)
            require(sha(receipt_path) == proof['sha256'] and receipt['passed'] is True and
                    receipt['case_id'] == case and receipt['candidate_id'] == candidate_id and
                    receipt['construction_sha256'] == candidate['construction_sha256'] and
                    receipt['scope'] == 'diagnostic software compatibility only' and
                    sha(HERE / proof['log']) == receipt['log_sha256'] and
                    sha(HERE / proof['negative_log']) == receipt['negative_log_sha256'],
                    'Selected compatibility proof differs')
            row = receipts[(case, candidate_id)]
            require(row['diagnostic_only'] is True and
                    sha(HERE / row['log']) == row['log_sha256'],
                    'Selected saved processing log differs')
            base = ROOT / '.runtime-work/c111256-update021-selected' / suffix / candidate_id
            processing = base / 'processed/v0001/processing.json'
            require(processing.is_file() and sha(processing) == row['processing_receipt_sha256'] and
                    read(processing)['physical_acceptance_claimed'] is False,
                    'Selected saved processing receipt differs')
            attempt = base / 'selected-attempt'
            selection = read(attempt / 'candidate-selection.json')
            require(selection['manifest_sha256'] == matrix['manifest_sha256'] and
                    selection['construction_sha256'] == candidate['construction_sha256'] and
                    selection['candidate_id'] == candidate_id,
                    'Selected attempt is bound to another manifest')
            if candidate_id == 'primary':
                data = read(construction)
                configs[suffix] = json.loads(next(item['content'] for item in data['files']
                                                   if item['path'] == 'config.json'))
                rows = [[json.loads(line) for line in (attempt / name).read_text().splitlines()]
                        if name.endswith('.jsonl') else read(attempt / name)
                        for name in SOURCES]
                hashes = {name: sha(attempt / name) for name in SOURCES}
                pairs[suffix] = (*rows, hashes)
    reference, contrast = configs['reference'], configs['contrast']
    require({key: value for key, value in reference.items() if key not in VARIABLE_KEYS} ==
            {key: value for key, value in contrast.items() if key not in VARIABLE_KEYS} and
            reference['case_suffix'] == 'reference' and contrast['case_suffix'] == 'contrast',
            'Selected pair changed a fixed construction setting')
    spec = importlib.util.spec_from_file_location('walk_pair', HERE / 'native/audit-walk-pair.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    comparison = module.audit(pairs['reference'], pairs['contrast'])
    return {'format': 'c111256-selected-cpu-pair-audit-v1',
            'manifest_sha256': matrix['manifest_sha256'],
            'selected_cases': 2, 'candidate_receipts_verified': 8,
            'comparison': comparison, 'original_physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(read(HERE / 'execution-manifest.json'),
                   read(HERE / 'update021-selected-process-saved-matrix.json'))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
