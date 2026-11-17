"""Reject corrupted limousine draft construction and proof records."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'limo_audit', Path(__file__).with_name('audit-limo-drafts-update038.py'))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def prove():
    original = target.read
    cases = (
        ('wrong actor', 'selected-primary/limo_below/construction.json',
         'native_blueprint', 'vehicle.mitsubishi.fusorosa'),
        ('false duration', 'update038-limo-at-primary-source-proof.json',
         'measured_duration_s', 1799.95),
        ('false offline pass', 'update038-limo-above-fallback2-offline.log',
         'offline_passed', False),
    )
    records = []
    for name, suffix, key, bad in cases:
        def corrupt(path):
            value = original(path)
            if str(path).endswith(suffix):
                value = dict(value)
                if key == 'native_blueprint':
                    files = [dict(row) for row in value['files']]
                    for row in files:
                        if row['path'] == 'config.json':
                            config = json.loads(row['content'])
                            config[key] = bad
                            row['content'] = json.dumps(config)
                    value['files'] = files
                else:
                    value[key] = bad
            return value
        target.read = corrupt
        try:
            target.audit()
        except ValueError as error:
            records.append({'mutation': name, 'rejected': True, 'error': str(error)})
        else:
            raise ValueError('Limo draft audit accepted mutation: ' + name)
        finally:
            target.read = original
    return {'passed': True, 'mutations': records}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
