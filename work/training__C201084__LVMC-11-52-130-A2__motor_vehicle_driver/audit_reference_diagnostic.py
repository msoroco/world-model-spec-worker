"""Independent diagnostic receipt and source-preservation audit for the draft primary."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(compatibility, saved):
    compatibility = Path(compatibility).resolve()
    saved = Path(saved).resolve()
    manifest = read(HERE/'draft-reference-manifest.json')
    contract = read(HERE/'draft-reference-measurement-contract.json')
    expected_case = HERE.name+'__reference'
    selected = manifest['cases'][0]
    positive = read(compatibility/'compatibility.json')
    processing = read(saved/'v0001/processing.json')
    if positive['passed'] is not True or positive['case_id'] != expected_case:
        raise ValueError('Compatibility case or result differs')
    if positive['construction_sha256'] != selected['construction_sha256']:
        raise ValueError('Compatibility construction differs')
    if positive['measurement_contract_sha256'] != sha(HERE/selected['measurement_contract']):
        raise ValueError('Measurement contract differs')
    if sorted(positive['measurement_keys']) != sorted(row['output_key'] for row in contract['requirements']):
        raise ValueError('Selected measurements incomplete')
    if positive['negative_removed'] != 'native-survey-readback.json' or not (
            contract['negative']['error_contains'] in
            (compatibility/'negative-analysis.log').read_text()):
        raise ValueError('Missing-source negative differs')
    if not {'four_camera_sources', 'lean_decoder', 'render', 'final_decode',
            'selected_measurements', 'negative_case_source'} <= set(positive['checks']):
        raise ValueError('Compatibility checks incomplete')
    if processing['passed'] is not True or processing['recorded_only'] is not True or \
            processing['originals_preserved'] is not True or processing['missing_evidence'] is not False or \
            processing['timestamp_joins'] != {'frames': 600, 'passed': True,
                                             'missing_original_trace_or_map': False}:
        raise ValueError('Saved processing incomplete')
    if processing['physical_acceptance_claimed'] or processing['legal_acceptance_claimed']:
        raise ValueError('Diagnostic claims acceptance')
    for relative, checksum in processing['original_source_hashes'].items():
        if sha(compatibility/relative) != checksum:
            raise ValueError('Original source changed: '+relative)
    result = read(saved/'v0001/analysis/result.json')
    if result['provenance_kind'] != 'synthetic_fixture' or not result['diagnostic_fixture'] or \
            result['accepted'] or result['physical_acceptance_claimed'] or result['legal_verdict_claimed']:
        raise ValueError('Saved result provenance or acceptance differs')
    channel = [json.loads(line) for line in
               (saved/'v0001/analysis/channels/vehicle_stops_in_posted_fire_lane.jsonl')
               .read_text().splitlines()]
    if len(channel) != 600 or any(row['value_basis'] != 'synthetic_authored_zone_only' or
                                  row['original_sign_text_verified'] or
                                  row['fire_code_designation_verified'] for row in channel):
        raise ValueError('Diagnostic channel misstates posting or frame count')
    return {'format': 'c201084-reference-diagnostic-audit', 'passed': True,
            'case_id': expected_case, 'construction_sha256': selected['construction_sha256'],
            'compatibility_sha256': sha(compatibility/'compatibility.json'),
            'saved_processing_sha256': sha(saved/'v0001/processing.json'),
            'source_count': len(processing['original_source_hashes']),
            'frames': len(channel), 'synthetic_only': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    import sys
    output = audit(sys.argv[1], sys.argv[2])
    target = HERE/'update102-reference-diagnostic-audit.json'
    target.write_text(json.dumps(output, indent=2, sort_keys=True)+'\n')
    print(json.dumps(output, sort_keys=True))
