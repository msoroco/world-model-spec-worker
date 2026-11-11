"""Check saved-processing ownership order on a synthetic sealed capture."""
import json
from pathlib import Path
import tempfile

from worker_exchange.common import sha
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


with tempfile.TemporaryDirectory(prefix='rider-lifecycle-fixture-') as tmp:
    root = Path(tmp)
    (root / 'construction.json').write_text('{}\n')
    (root / 'runner.py').write_text('pass\n')
    (root / 'trace.jsonl').write_text('{"frame":1}\n')
    revision = {'construction_sha256': sha(root / 'construction.json'),
                'runner_sha256': sha(root / 'runner.py')}
    write(root / 'capture-seal.json', {'events': ['capture_finished', 'encoders_closed',
          'restoration_verified'], 'native_revision': revision,
          'sources': {'trace.jsonl': sha(root / 'trace.jsonl')}})
    try:
        _closure(root, None, 'native', False)
    except (ValueError, OSError):
        pass
    else:
        raise AssertionError('owner-release omission accepted')
    try:
        acknowledge_owner_release(root, root / 'owner-release.json', True)
    except ValueError:
        pass
    else:
        raise AssertionError('owner release before exit accepted')
    record_native_exit(root)
    acknowledge_owner_release(root, root / 'owner-release.json', True)
    _closure(root, root / 'owner-release.json', 'native', False)
    (root / 'trace.jsonl').write_text('{"frame":2}\n')
    try:
        _closure(root, root / 'owner-release.json', 'native', False)
    except ValueError:
        pass
    else:
        raise AssertionError('changed sealed original accepted')
print(json.dumps({'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
      'native_exit', 'owner_released', 'saved_processing_started'],
      'missing_owner_release_rejected': True, 'premature_release_rejected': True,
      'changed_original_rejected': True, 'fixture_only': True}))
