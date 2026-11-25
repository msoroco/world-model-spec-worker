"""Independent CPU comparison of retained selected diagnostic constructions."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'
ASSIGNMENT = ROOT.name
GROUPS = {
    'witness_comparison': ('selected-paragraph-d', ('witness_1', 'witness_2')),
    'exception_1_comparison': ('exception-1', ('exception_1_1', 'exception_1_2')),
    'exception_3_comparison': ('current-c1', ('exception_3_1', 'exception_3_2')),
    'exception_4_comparison': ('exception-4', ('exception_4_1', 'exception_4_2')),
    'exception_5_comparison': ('subsection-4', ('exception_5_1', 'exception_5_2')),
    'numeric_1_comparison': ('numeric-boundary', ('numeric_1_0', 'numeric_1_1', 'numeric_1_2')),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    plan_path = ROOT / 'case-plan.json'
    plan = read(plan_path)
    rows = []
    by_id = {row['comparison_id']: row for row in plan['comparisons']}
    for name, (folder_name, suffixes) in GROUPS.items():
        comparison_id = ASSIGNMENT + '__' + name
        plan_row = by_id[comparison_id]
        assert plan_row['case_ids'] == [ASSIGNMENT + '__' + suffix for suffix in suffixes]
        folder = NATIVE / folder_name
        manifest_path = folder / 'manifest.json'
        manifest = read(manifest_path)
        assert {row['case_id'] for row in manifest['cases']} == set(plan_row['case_ids'])
        cases = []
        constructions = []
        for suffix in suffixes:
            case_dir = folder / suffix
            construction_path = case_dir / 'primary' / 'construction.json'
            construction = read(construction_path)
            entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + suffix))
            assert entry['construction_sha256'] == sha(construction_path)
            assert construction['case_id'] == entry['case_id']
            assert construction['cell_id'] == 'C146314'
            assert construction['actor'] == 'motor_vehicle_driver'
            assert construction['law_id'] == 'NRS-484B-210-1'
            assert construction['termination_rules']['requested_frames'] == 600
            assert construction['original_native_observed'] is False
            constructions.append(construction)
            compatibility = case_dir / 'compatibility.json'
            saved = case_dir / 'saved-processing.json'
            processing = read(saved)
            assert processing['recorded_only'] is True
            result_path = Path(processing['result'])
            assert result_path.is_file() and sha(result_path) == processing['result_sha256']
            measured = read(result_path)['measured_values']
            assert measured['frames_joined'] == 600
            assert measured['original_native_observed'] is False
            cases.append({'case_id': entry['case_id'],
                          'construction': str(construction_path.relative_to(ROOT)),
                          'construction_sha256': sha(construction_path),
                          'compatibility_sha256': sha(compatibility),
                          'saved_processing_sha256': sha(saved),
                          'saved_result_sha256': sha(result_path),
                          'source_measured_values': measured})
        assert len({item['construction_sha256'] for item in cases}) == len(cases)
        channels = [[(item['name'], item['sampling_rate_hz'])
                     for item in c['recording_description']['channels']]
                    for c in constructions]
        assert all(channel == channels[0] for channel in channels)
        assert all(c['mechanisms']['road'] == constructions[0]['mechanisms']['road']
                   for c in constructions)
        if name == 'exception_3_comparison':
            assert [item['source_measured_values']['observed_shoulder_centerline_span_m']
                    for item in cases] == [61.06, 60.96]
        if name == 'numeric_1_comparison':
            assert [item['source_measured_values']['observed_shoulder_centerline_span_m']
                    for item in cases] == [60.86, 60.96, 61.06]
        rows.append({'comparison_id': comparison_id,
                     'status': 'cpu_construction_and_saved_join_checked',
                     'fixed_conditions_checked': ['assignment_id', 'cell_id', 'actor',
                         'law_id', '600_frame_policy', 'recording_channel_names_and_rates',
                         'authored_road_mechanism'],
                     'deliberate_differences': plan_row['deliberate_differences'],
                     'cases': cases,
                     'physical_outcome_comparison_complete': False,
                     'legal_verdict': None})
    pending = by_id[ASSIGNMENT + '__exception_2_comparison']
    assert len(pending['case_ids']) == 2
    output = {'format': 'c146314-selected-comparison-cpu-v1',
              'assignment_id': ASSIGNMENT, 'case_plan_sha256': sha(plan_path),
              'comparisons': rows,
              'unbound_comparison': {'comparison_id': pending['comparison_id'],
                  'status': 'paragraph_b_unbound',
                  'source_proof': 'native/paragraph-b-binding-proof.json',
                  'source_proof_sha256': sha(NATIVE / 'paragraph-b-binding-proof.json')},
              'physical_or_legal_acceptance': False}
    path = NATIVE / 'selected-comparison-cpu-audit.json'
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print('PASS six selected construction/recorded-only comparisons; paragraph (b) unbound')


if __name__ == '__main__':
    main()
