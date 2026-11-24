"""Independently compare synthetic marked-crossing source and current-runtime proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = ('marked', 'outside')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit():
    proof = read(HERE / 'crossref-060a-native/proof.json')
    plan = read(HERE / 'case-plan.json')
    manifest = read(HERE / 'crossref-060a-manifest.json')
    case_ids = [HERE.name + '__crossref_lvmc_11_30_060_a_' + label for label in LABELS]
    pairs = [x for x in plan['comparisons'] if set(x['case_ids']) == set(case_ids)]
    if len(pairs) != 1 or len(proof['records']) != 2 or len(manifest['cases']) != 2:
        raise ValueError('Exactly one two-case marked-crossing comparison required')
    sources = []
    for label, case_id in zip(LABELS, case_ids):
        row = next(x for x in proof['records'] if x['case_id'] == case_id)
        entry = next(x for x in manifest['cases'] if x['case_id'] == case_id)
        folder = HERE / 'crossref-060a-native' / label
        measurement = read(folder / 'source-measurement.json')
        construction = HERE / entry['construction']
        if entry['construction_sha256'] != digest(construction) or row['construction_sha256'] != digest(construction):
            raise ValueError('Primary construction binding differs')
        fallback = entry['candidates'][0]
        if fallback['id'] != 'fallback1' or fallback['construction_sha256'] != digest(HERE / fallback['construction']):
            raise ValueError('Fallback construction binding differs')
        if row['source_measurement_sha256'] != digest(folder / 'source-measurement.json'):
            raise ValueError('Source measurement binding differs')
        if measurement['frames'] != 600 or measurement['source_kind'] != 'synthetic_scene_request':
            raise ValueError('Source frame count or provenance differs')
        if measurement['marking_relation_at_entry'] != ('inside_authored_marking' if label == 'marked' else 'outside_authored_marking'):
            raise ValueError('Crossing relation differs')
        if any((measurement['physical_crossing_observed'],
                measurement['marking']['original_paint_pixels_observed'],
                measurement['vehicle_right_of_way_reviewed'],
                measurement['designated_place_prohibition_reviewed'])) or measurement['legal_applicability_conclusion'] is not None:
            raise ValueError('Synthetic crossing overclaims physical or legal conclusion')
        for name, expected in row['current_runtime_proof_hashes'].items():
            if digest(folder / 'proofs' / name) != expected:
                raise ValueError('Primary proof hash differs')
        for name, expected in row['fallback1_current_runtime_proof_hashes'].items():
            if digest(HERE / 'crossref-060a-fallback1' / label / 'proofs' / name) != expected:
                raise ValueError('Fallback proof hash differs')
        if not all(row.get(k) for k in ('public_compatibility_positive_passed',
                                       'public_missing_source_negative_rejected',
                                       'recorded_only_process_saved_passed',
                                       'fallback1_public_positive_passed',
                                       'fallback1_missing_source_negative_rejected',
                                       'fallback1_recorded_only_process_saved_passed')):
            raise ValueError('Current-runtime proof path incomplete')
        sources.append(measurement)
    if sources[0]['vehicle_trace_sha256'] != sources[1]['vehicle_trace_sha256']:
        raise ValueError('Controlled vehicle trace differs')
    if sources[0]['roadway_entry_frame'] != sources[1]['roadway_entry_frame']:
        raise ValueError('Crossing timing differs')
    if sources[0]['crossing_y_m'] == sources[1]['crossing_y_m']:
        raise ValueError('Crossing-location variable unchanged')
    return {'format': 'c230222-crossref-060a-comparison-proof-v1',
            'case_ids': case_ids, 'comparison_id': pairs[0]['comparison_id'],
            'vehicle_trace_sha256': sources[0]['vehicle_trace_sha256'],
            'deliberate_difference': 'synthetic crossing y and authored-marking relation',
            'public_positive_count': 4, 'missing_source_negative_count': 4,
            'recorded_only_saved_count': 4, 'original_native_observed': False,
            'legal_applicability_conclusion': None}


if __name__ == '__main__':
    path = HERE / 'crossref-060a-comparison-proof.json'
    path.write_text(json.dumps(audit(), indent=2) + '\n')
    print(json.dumps({'comparison': 'pass', 'proof': path.name}))
