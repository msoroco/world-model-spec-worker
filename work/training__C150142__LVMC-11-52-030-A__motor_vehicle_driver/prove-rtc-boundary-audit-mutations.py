"""Check RTC boundary audit rejects missing and altered saved evidence."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'rtc_boundary_audit', Path(__file__).with_name('audit-rtc-boundaries-update037.py'))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def prove():
    original = target.read
    cases = (
        ('missing negative rejection', 'update037-rtc-no-loading-primary-negative.json',
         'rejected', False),
        ('wrong above duration', 'update037-rtc-above-primary-pinned-saved-v1.json',
         'reported_duration_s', 1800.0),
        ('wrong no-loading activity', 'update037-rtc-no-loading-primary-pinned-saved-v1.json',
         'reported_activity_events', 1),
    )
    records = []
    for name, filename, key, bad in cases:
        def corrupt(path):
            value = original(path)
            if Path(path).name == filename:
                value = dict(value)
                value[key] = bad
            return value
        target.read = corrupt
        try:
            target.audit()
        except ValueError as error:
            records.append({'mutation': name, 'rejected': True, 'error': str(error)})
        else:
            raise ValueError('RTC boundary audit accepted mutation: ' + name)
        finally:
            target.read = original
    return {'passed': True, 'mutations': records}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
