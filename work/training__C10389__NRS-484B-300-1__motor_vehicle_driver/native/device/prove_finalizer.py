"""Reproduce source-bound 600-frame saved-finalizer CPU diagnostics."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from finalize import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def staged(scratch, suffix, label=None):
    bundle = HERE / 'offline' / 'bundles' / suffix / 'primary'
    raw = HERE / 'offline' / 'raw-fixtures' / suffix / 'primary'
    target = scratch / (label or suffix)
    shutil.copytree(bundle, target)
    for source in raw.iterdir():
        shutil.copy2(source, target / source.name)
    return target


def rejected(folder, expected, synthetic=False):
    try:
        analyze(folder, folder / 'analysis-report.json', synthetic_cpu=synthetic)
    except (ValueError, FileNotFoundError) as error:
        if expected not in str(error):
            raise AssertionError('Wrong source rejection: ' + str(error)) from error
        return str(error)
    raise AssertionError('Source-negative finalization passed')


def prove():
    with tempfile.TemporaryDirectory(prefix='c10389-finalizer-', dir=ROOT / '.runtime-work') as name:
        scratch = Path(name)
        positives = {}
        for suffix in ('probe_1', 'probe_2'):
            attempt = staged(scratch, suffix)
            before = {p.name: digest(p) for p in attempt.iterdir() if p.is_file()}
            analysis = analyze(attempt, attempt / 'analysis-report.json', synthetic_cpu=True)
            after = {p.name: digest(p) for p in attempt.iterdir() if p.is_file() and p.name in before}
            if before != after:
                raise AssertionError('Original diagnostic source modified')
            result = json.loads((attempt / 'result.json').read_text())
            if result['accepted'] or result['legal_verdict_claimed'] or result['setup_confirmed']:
                raise AssertionError('Synthetic diagnostic promoted to Native evidence')
            if not result['target_checks'][0]['matched']:
                raise AssertionError('Measured requested response differs')
            positives[suffix] = {'source_frames': 600,
                'stopped_before_device_frames': analysis['measurements']['stop_before_device_frames'],
                'body_at_device_station_frames': analysis['measurements']['body_at_device_station_frames'],
                'source_preserved': True, 'result_schema_validated': True}
        missing = staged(scratch, 'probe_1', 'missing_actors')
        (missing / 'native-raw-actors.jsonl').unlink()
        missing_error = rejected(missing, 'native-raw-actors.jsonl', synthetic=True)
        kind = staged(scratch, 'probe_2', 'wrong_kind')
        kind_error = rejected(kind, 'Native source kind differs', synthetic=False)
        original = staged(scratch, 'probe_1', 'no_media')
        mapping = json.loads((original / 'native-map-readback.json').read_text())
        mapping['source_kind'] = 'original_native'
        (original / 'native-map-readback.json').write_text(json.dumps(mapping) + '\n')
        media_error = rejected(original, 'Missing required source: overview.mkv', synthetic=False)
        return {'format': 'c10389-source-bound-finalizer-cpu-proof-v1',
            'positive': positives,
            'missing_actors_negative': missing_error,
            'synthetic_as_original_negative': kind_error,
            'original_without_media_negative': media_error,
            'original_native_observed': False, 'delivery_ready': False,
            'finalizer_sha256': digest(HERE / 'finalize.py')}


if __name__ == '__main__':
    proof = prove()
    path = HERE / 'offline' / 'finalizer-proof.json'
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print(json.dumps(proof, allow_nan=False))
