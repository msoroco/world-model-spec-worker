"""Check eight current selected synthetic business/mail source contrasts."""
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
PAIRS = {
    'armored_car_sign_exception': ('sign_present', False, True),
    'armored_car_unsigned_business_pair': ('business_activity', True, False),
    'armored_car_signed_business_pair': ('business_activity', True, False),
    'emergency_vehicle_sign_exception': ('sign_present', False, True),
    'emergency_vehicle_unsigned_business_pair': ('business_activity', True, False),
    'emergency_vehicle_signed_business_pair': ('business_activity', True, False),
    'mailbox_adjacency': ('mailbox_present', True, False),
    'mail_activity': ('mail_deposit', True, False),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def main():
    manifest = WORK / 'execution-manifest.json'
    manifest_sha = sha(manifest)
    selected = {item['case_id']: item for item in read(manifest)['cases']}
    plan = {item['comparison_id'].rsplit('__', 1)[-1]: item
            for item in read(WORK / 'case-plan.json')['comparisons']}
    saved = {row['case']: row for row in read(WORK / 'current-short-selected-saved-index.json')['rows']}
    rows = []
    for name, (variable, left_expected, right_expected) in PAIRS.items():
        pair = plan[name]
        require(pair['deliberate_differences'], 'Missing planned difference: ' + name)
        observations = []
        for case_id in pair['case_ids']:
            slug = case_id.rsplit('__', 1)[-1]
            row = saved[slug]
            require(row['manifest_sha256'] == manifest_sha and row['exit_code'] == 0,
                    'Short saved proof differs: ' + slug)
            analysis = Path(row['scratch_result']) / 'v0001/analysis'
            require(REPO / '.runtime-work' in analysis.resolve().parents,
                    'Selected source path is outside scratch')
            selection = read(analysis / 'candidate-selection.json')
            require(selection['manifest_sha256'] == manifest_sha and
                    selection['case_id'] == case_id and
                    selection['construction_sha256'] == selected[case_id]['construction_sha256'],
                    'Current selected construction differs: ' + slug)
            processing = Path(row['scratch_result']) / 'v0001/processing.json'
            require(sha(processing) == row['processing']['processing']['sha256'],
                    'Saved processing hash differs: ' + slug)
            measured = read(analysis / 'result.json')['measured_values']['signed_curb_observation']
            require(measured['source_kind'] == 'synthetic_native_sample' and
                    measured['physical_acceptance_claimed'] is False and
                    measured['statutory_exception_applies'] is None,
                    'Diagnostic source overclaims a legal result: ' + slug)
            map_data = read(analysis / 'native-map-readback.json')
            events = {event['name'] for event in measured['recorded_activity_events']}
            observations.append({'case_id': case_id, 'slug': slug,
                'paint': [map_data[k] for k in ('paint_color','red_curb_start_x_m',
                                                'red_curb_end_x_m','curb_y_m')],
                'frames': measured['frames'],
                'duration_s': measured['red_curb_stationary_duration_s'],
                'blueprint': measured['native_blueprint'],
                'service_class': measured['declared_service_class'],
                'sign_present': measured['sign_present'],
                'mailbox_present': measured['mailbox_present'],
                'business_activity': 'business_activity' in events,
                'mail_deposit': 'mail_deposit' in events,
                'processing_sha256': sha(processing)})
        left, right = observations
        for key in ('paint','frames','duration_s','blueprint','service_class'):
            require(left[key] == right[key], 'Controlled source differs: ' + name + ' ' + key)
        for key in ('sign_present','mailbox_present','business_activity','mail_deposit'):
            if key != variable:
                require(left[key] == right[key], 'Unplanned source contrast: ' + name + ' ' + key)
        require((left[variable], right[variable]) == (left_expected, right_expected),
                'Planned source contrast missing: ' + name)
        rows.append({'comparison_id': pair['comparison_id'], 'variable': variable,
                     'source_observations': observations,
                     'source_contrast_passed': True,
                     'original_native_observed': False,
                     'legal_verdict': None})
    print(json.dumps({'format': 'c150142-current-short-exception-comparisons-v1',
                      'passed': len(rows) == 8, 'manifest_sha256': manifest_sha,
                      'rows': rows, 'source_kind': 'synthetic_native_sample',
                      'physical_acceptance_claimed': False,
                      'legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
