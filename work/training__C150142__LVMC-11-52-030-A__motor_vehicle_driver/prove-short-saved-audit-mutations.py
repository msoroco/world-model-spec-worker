"""Check independent short saved audit rejects corrupt proof records."""
import json
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('short_saved_audit',
    Path(__file__).with_name('audit-short-saved-update037.py'))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def prove():
    original = target.read
    cases = (
        ('missing source rejection', 'update037-reference-primary-saved-negative.json', 'rejected', False),
        ('wrong candidate compatibility', 'update037-contrast-fallback2-candidate-compat.json', 'candidate_id', 'primary'),
        ('wrong saved frame count', 'update037-reference-fallback3-pinned-saved.json', 'frames', 239),
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
            raise ValueError('Audit accepted mutation: ' + name)
        finally:
            target.read = original
    return {'passed': True, 'mutations': records}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
