"""Independently audit pinned synthetic tour-bus fallback evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ALLOWED_CONFIG_CHANGES = {'candidate_id', 'risk_trigger', 'requested_target_x_m',
                          'camera_policy', 'tracks_sha256'}
BOUNDARIES = {'below': (36120, 1799.95, 'below'),
              'at': (36121, 1800, 'at'),
              'above': (36122, 1800.05, 'above'),
              'no_loading': (36121, 1800, 'at')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(suffix='below', service='tour_bus'):
    if suffix not in BOUNDARIES:
        raise ValueError('Unsupported pinned tour-bus boundary')
    if service not in ('tour_bus', 'shuttle_bus', 'rtc_bus'):
        raise ValueError('Unsupported pinned signed-bus audit')
    frames, duration, boundary = BOUNDARIES[suffix]
    update = {'below': '032', 'at': '033', 'above': '034',
              'no_loading': '034'}[suffix]
    slug = suffix.replace('_', '-')
    case = ROOT.name + '__' + service + '_' + suffix
    prefix = ({'tour_bus': 'c150142-tour-bus-pinned-saved-',
               'shuttle_bus': 'c150142-shuttle-',
               'rtc_bus': 'c150142-rtc-'}[service] + slug + '-')
    fixed = {'capture_frames': frames, 'requested_approach_frames': 120,
             'requested_stationary_duration_s': duration,
             'requested_boundary': boundary, 'rate_hz': 20}
    manifest = read(ROOT / {
        'tour_bus': 'execution-manifest-diagnostic-tour_bus_below-draft.json',
        'shuttle_bus': 'execution-manifest-diagnostic-shuttle_bus_below-draft.json',
        'rtc_bus': 'execution-manifest-diagnostic-rtc_bus_below-draft.json',
    }[service])
    entry = next(e for e in manifest['cases'] if e['case_id'] == case)
    fallback_entries = {c['id']: c for c in entry['candidates']}
    require(set(fallback_entries) == {'fallback1', 'fallback2', 'fallback3'},
            'Expected exactly three source-bound fallback candidates')
    triggers = {(c['trigger']['metric'], c['trigger']['failure_condition'])
                for c in fallback_entries.values()}
    require(len(triggers) == 3, 'Fallback physical-risk triggers overlap')
    records = []
    configs = {}
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        stem = ((('result-v7' if suffix == 'below' else 'result-v1')
                 if service == 'tour_bus' else
                 'primary-result-v2' if service == 'shuttle_bus' and suffix == 'below'
                 else 'primary-result-v1')
                if candidate == 'primary' else candidate + '-result-v1')
        version = REPO / '.runtime-work' / (prefix + stem) / 'v0001'
        if service == 'rtc_bus':
            summary_name = f'update037-rtc-{slug}-{candidate}-pinned-saved-v1.json'
            negative_name = f'update037-rtc-{slug}-{candidate}-negative.json'
        elif service == 'shuttle_bus':
            summary_name = ('update035-shuttle-below-primary-pinned-saved-v2.json'
                            if suffix == 'below' and candidate == 'primary' else
                            f'update035-shuttle-below-{candidate}-pinned-saved-v1.json'
                            if suffix == 'below' else
                            f'update{"036" if suffix == "at" else "037"}-shuttle-{slug}-{candidate}-pinned-saved-v1.json')
            negative_name = (f'update035-shuttle-below-{candidate}-negative.json'
                             if suffix == 'below' else
                             f'update{"036" if suffix == "at" else "037"}-shuttle-{slug}-{candidate}-negative.json')
        else:
            summary_name = (('update032-below-primary-pinned-saved-recheck.json'
                             if suffix == 'below' else f'update033-tour-bus-{slug}-primary-recheck.json')
                            if candidate == 'primary' else
                            f'update{update}-{slug}-{candidate}-pinned-saved-v1.json')
            negative_name = (f'update032-below-{candidate}-negative.json'
                             if suffix == 'below' else
                             (f'update032-tour-bus-{slug}-primary-negative.json'
                              if candidate == 'primary' else
                              f'update{update}-{slug}-{candidate}-negative.json'))
        summary = read(ROOT / summary_name)
        processing = read(version / 'processing.json')
        selected = read(version / 'analysis/candidate-selection.json')
        negative = read(ROOT / negative_name)
        config = read(version / 'analysis/config.json')
        expected_sha = (entry['construction_sha256'] if candidate == 'primary'
                        else fallback_entries[candidate]['construction_sha256'])
        require(processing['passed'] is True and
                processing['candidate_id'] == selected['candidate_id'] == candidate and
                processing['analysis_revision']['construction_sha256'] ==
                selected['construction_sha256'] == expected_sha,
                'Pinned candidate identity differs: ' + candidate)
        require(summary['processing_sha256'] == sha(version / 'processing.json') and
                summary['processing_passed'] is True and
                summary['timestamp_join_frames'] == summary['final_decode_frames'] == frames and
                summary['reported_duration_s'] == duration and
                summary['reported_boundary'] == boundary and
                summary['reported_activity_events'] == (0 if suffix == 'no_loading' else 1) and
                len(summary['source_decodes']) == 4 and
                all(s['passed'] and s['frames'] == frames for s in summary['source_decodes']) and
                'full_core=true' in summary['decoder_stdout'],
                'Full pinned CPU proof differs: ' + candidate)
        require(negative['rejected'] is True and
                negative['candidate_id'] == candidate and
                negative['positive_processing_sha256'] == summary['processing_sha256'] and
                negative['removed'] == 'native-map-readback.json',
                'Missing-source rejection differs: ' + candidate)
        require(all(config.get(k) == v for k, v in fixed.items()) and
                config['case_id'] == case,
                'Fixed law-boundary configuration differs: ' + candidate)
        configs[candidate] = config
        record = {'candidate_id': candidate,
                        'construction_sha256': expected_sha,
                        'processing_sha256': summary['processing_sha256'],
                        'summary_sha256': sha(ROOT / summary_name),
                        'negative_sha256': sha(ROOT / negative_name),
                        'target_x_m': config['requested_target_x_m'],
                        'camera_policy': config['camera_policy']}
        if suffix == 'no_loading':
            inventory_name = {
                'tour_bus': f'update034-no-loading-{candidate}-inventory-negative.json',
                'shuttle_bus': f'update037-shuttle-no-loading-{candidate}-inventory-negative.json',
                'rtc_bus': f'update037-rtc-no-loading-{candidate}-inventory-negative.json',
            }[service]
            inventory = read(ROOT / inventory_name)
            require(inventory['rejected'] is True and
                    inventory['candidate_id'] == candidate and
                    inventory['positive_processing_sha256'] == summary['processing_sha256'] and
                    inventory['removed'] == 'native-passenger-inventory.jsonl',
                    'Missing passenger-inventory rejection differs: ' + candidate)
            record['inventory_negative_sha256'] = sha(ROOT / inventory_name)
        records.append(record)
    base = configs['primary']
    for candidate in fallback_entries:
        changed = {key for key in base.keys() | configs[candidate].keys()
                   if base.get(key) != configs[candidate].get(key)}
        require(changed <= ALLOWED_CONFIG_CHANGES and changed &
                {'requested_target_x_m', 'camera_policy'},
                'Fallback changes fixed scenario conditions: ' + candidate)
    require(configs['fallback1']['requested_target_x_m'] < base['requested_target_x_m'] <
            configs['fallback3']['requested_target_x_m'] and
            configs['fallback2']['camera_policy'] != base['camera_policy'],
            'Fallback mitigations do not match physical-risk triggers')
    return {'format': ('c150142-' + service.replace('_', '-') + '-' +
                       slug + '-fallback-audit-v1'),
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'passed': True,
            'case_id': case, 'records': records,
            'distinct_triggers': sorted(triggers)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=sorted(BOUNDARIES), default='below')
    parser.add_argument('--service', choices=('tour_bus', 'shuttle_bus', 'rtc_bus'),
                        default='tour_bus')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.service), sort_keys=True))
