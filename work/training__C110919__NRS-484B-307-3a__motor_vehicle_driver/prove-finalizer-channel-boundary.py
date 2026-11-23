"""Exercise 30-second finalizer channel reconstruction from raw saved sources."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from finalize import prepare_channels
spec = importlib.util.spec_from_file_location('raw_fixture', HERE / 'prove-raw-channels.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
make_source = fixture.make_source


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    positives = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c110919-finalizer-') as temp:
        base = Path(temp)
        for case in ('witness_1', 'witness_2'):
            attempt = base / case
            make_source(attempt, case)
            config = json.loads((attempt / 'config.json').read_text())
            before = {str(p.relative_to(attempt)): digest(p) for p in attempt.rglob('*') if p.is_file()}
            result = prepare_channels(attempt, config)
            after = {name: digest(attempt / name) for name in before}
            assert before == after and result['mode'] == 'raw_native_30s'
            assert len(result['channel_hashes']) == 10
            positives.append({'case': case, 'raw_sources_unchanged': True,
                              'derived_channels': 10, 'frames': 600})
        injected = base / 'injected'
        shutil.copytree(base / 'witness_1', injected)
        config = json.loads((injected / 'config.json').read_text())
        try:
            prepare_channels(injected, config)
        except ValueError as exc:
            assert 'Derived channel output already exists' in str(exc)
        else:
            raise AssertionError('Accepted injected channel files')
        missing = base / 'missing'
        shutil.copytree(base / 'witness_2', missing)
        shutil.rmtree(missing / 'channels')
        (missing / 'native_samples.jsonl').unlink()
        try:
            prepare_channels(missing, json.loads((missing / 'config.json').read_text()))
        except ValueError as exc:
            assert 'Missing retained Native source' in str(exc)
        else:
            raise AssertionError('Accepted absent raw Native source')
    return {'format': 'c110919-finalizer-channel-boundary-proof-v1',
            'positives': positives, 'negative_rejections': 2,
            'physical_observation_claimed': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
