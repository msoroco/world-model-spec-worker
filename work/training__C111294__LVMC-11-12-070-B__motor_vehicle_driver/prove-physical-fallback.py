"""Check that an upstream-spawn fallback changes only the requested engineering knob."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = 'THROUGH_START_AUTHORED_Y_M = 65.0'
NEW = 'THROUGH_START_AUTHORED_Y_M = 70.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(construction):
    return {item['path']: item['content'] for item in construction['files']}


def check(primary, fallback):
    first, second = files(primary), files(fallback)
    if set(first) != set(second) or 'live_capture.py' not in first:
        raise ValueError('Fallback source inventory changed')
    if first['live_capture.py'].count(OLD) != 1:
        raise ValueError('Primary through start differs')
    if second['live_capture.py'] != first['live_capture.py'].replace(OLD, NEW):
        raise ValueError('Fallback changed more than through start')
    if any(second[name] != content for name, content in first.items()
           if name != 'live_capture.py'):
        raise ValueError('Fallback changed fixed source or controller')
    if fallback['recording_description'] != primary['recording_description']:
        raise ValueError('Fallback recording description differs')
    if fallback.get('fallback_changed_knobs') != ['through_start_authored_y_m']:
        raise ValueError('Fallback knob declaration differs')
    return True


def main():
    receipt = {'format': 'c111294-physical-fallback-source-proof-v1',
               'passed': True, 'original_native_observed': False,
               'legal_verdict_claimed': False,
               'changed_knob': 'through_start_authored_y_m',
               'failure_trigger': {'source': 'native_samples.jsonl',
                                   'metric': 'through body position at first requested yield hold',
                                   'failure_condition': 'observed full through body overshoots the source-reviewed safe hold location before the entrant clears'},
               'cases': [], 'negative_rejections': []}
    for number, folder in ((1, 'draft-primary'), (2, 'draft-controlled')):
        a = HERE / folder / 'construction.json'
        b = HERE / 'cases' / f'probe_{number}' / 'fallback1' / 'construction.json'
        primary, fallback = json.loads(a.read_text()), json.loads(b.read_text())
        check(primary, fallback)
        wrong = json.loads(json.dumps(fallback))
        next(item for item in wrong['files'] if item['path'] == 'runner.py')['content'] += '# changed\n'
        try:
            check(primary, wrong)
        except ValueError as exc:
            receipt['negative_rejections'].append(str(exc))
        else:
            raise AssertionError('Changed controller passed fallback source check')
        receipt['cases'].append({'case_id': primary['case_id'],
                                 'primary_sha256': sha(a), 'fallback1_sha256': sha(b),
                                 'source_delta_verified': True})
    path = HERE / 'physical-fallback-source-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(receipt['cases']),
                      'negative_rejections': len(receipt['negative_rejections']),
                      'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
