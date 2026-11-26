"""Check exact request meters and fail-closed original-source separation."""
import copy
import hashlib
import json
from pathlib import Path

from taxi_loading import measure

BASE = Path(__file__).resolve().parents[1]


def reject(rows, source_kind):
    try:
        measure(rows, source_kind)
    except ValueError:
        return True
    raise AssertionError('Invalid measurement passed: ' + source_kind)


def main():
    manifest = json.loads((BASE / 'draft-native-manifest.json').read_text())
    reports = []
    for case in manifest['cases']:
        path = BASE / case['construction']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case['construction_sha256']
        files = {item['path']: item['content'] for item in json.loads(path.read_text())['files']}
        rows = [json.loads(line) for line in files['requested-track.jsonl'].splitlines()]
        measured = measure(rows, 'authored_native_request')
        checks = {}
        for name, mutate in (
            ('missing_frame', lambda x: x.pop()),
            ('wrong_time', lambda x: x[10].update(time_s=9)),
            ('missing_taxi', lambda x: x[10].pop('requested_taxi_identity')),
            ('wrong_stand', lambda x: x[10].update(requested_stand_location='inside_designated_stand')),
            ('moving_taxi', lambda x: x[10].update(requested_speed_mps=1)),
            ('missing_door', lambda x: x[10].pop('requested_door_open')),
            ('missing_occupant', lambda x: x[10].pop('requested_occupant_count')),
            ('missing_activity', lambda x: x[200].pop('requested_activity')),
        ):
            changed = copy.deepcopy(rows)
            mutate(changed)
            checks[name] = reject(changed, 'authored_native_request')
        changed = copy.deepcopy(rows)
        for row in changed:
            row['source_kind'] = 'original_native'
            row['taxi_identity_review'] = {}
            row['participant_activity_review'] = {}
            row['other_regulations_review'] = {}
        checks['request_cannot_claim_original_with_empty_reviews'] = reject(changed, 'original_native')
        reports.append({'case_id': case['case_id'],
                        'construction_sha256': case['construction_sha256'],
                        'request_measurement': measured,
                        'negative_checks': checks})
    assert reports[0]['request_measurement']['requested_activity'] == 'passenger_loading'
    assert reports[1]['request_measurement']['requested_activity'] == 'merchandise_loading'
    assert all(all(r['negative_checks'].values()) for r in reports)
    output = {'assignment_id': BASE.name, 'source_kind': 'authored_native_request',
              'original_native_observed': False, 'reports': reports,
              'original_source_requirement': 'Native capture plus participant, stand-designation and other-regulation source hashes'}
    (BASE / 'native/request-source-negative-proof.json').write_text(
        json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(reports),
                      'negative_checks': sum(len(r['negative_checks']) for r in reports)}))


if __name__ == '__main__':
    main()
