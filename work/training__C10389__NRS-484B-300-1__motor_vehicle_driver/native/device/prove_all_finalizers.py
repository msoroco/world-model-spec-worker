"""Exercise all eight exact draft finalizers against retained 600-frame sources.

This is a diagnostic source-join proof. It does not confer official-device or
physical provenance on any authored fixture.
"""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from finalize import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE_NAMES = ('native-map-readback.json', 'native-raw-actors.jsonl',
                'video_frames.jsonl', 'frame-review.jsonl',
                'native-capture-report.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(scratch, case, candidate, tag):
    bundle = HERE / 'offline' / 'bundles' / case / candidate
    raw = HERE / 'offline' / 'raw-fixtures' / case / candidate
    destination = scratch / tag
    shutil.copytree(bundle, destination)
    for item in raw.iterdir():
        if item.is_file():
            shutil.copy2(item, destination / item.name)
    return destination


def reject(folder, wanted):
    try:
        analyze(folder, folder / 'analysis-report.json', synthetic_cpu=True)
    except (ValueError, FileNotFoundError) as error:
        if wanted not in str(error):
            raise AssertionError(f'Unexpected rejection: {error}') from error
        return str(error)
    raise AssertionError('Malformed source was accepted')


def run():
    entries = []
    with tempfile.TemporaryDirectory(prefix='c10389-all-finalizers-',
                                     dir=ROOT / '.runtime-work') as temporary:
        scratch = Path(temporary)
        for case in ('probe_1', 'probe_2'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                label = f'{case}-{candidate}'
                attempt = stage(scratch, case, candidate, label)
                original = {name: sha(attempt / name) for name in SOURCE_NAMES}
                report = analyze(attempt, attempt / 'analysis-report.json',
                                 synthetic_cpu=True)
                result = json.loads((attempt / 'result.json').read_text())
                if any(sha(attempt / name) != checksum
                       for name, checksum in original.items()):
                    raise AssertionError('Finalizer rewrote source evidence')
                if result['accepted'] or result['legal_verdict_claimed']:
                    raise AssertionError('Synthetic diagnostic claimed acceptance')
                if report['source_hashes'] != original:
                    raise AssertionError('Report lacks exact source hashes')
                negatives = {}
                for name in ('native-raw-actors.jsonl', 'frame-review.jsonl'):
                    broken = stage(scratch, case, candidate, f'{label}-missing-{name}')
                    (broken / name).unlink()
                    negatives[name] = reject(broken, name)
                entries.append({
                    'case_id': result['case_id'], 'candidate_id': candidate,
                    'source_hashes': original,
                    'measurements': report['measurements'],
                    'target_matched': result['target_checks'][0]['matched'],
                    'missing_source_rejections': negatives,
                    'original_source_preserved': True,
                    'physical_acceptance_claimed': False,
                })
    return {'format': 'c10389-all-draft-finalizers-cpu-proof-v1',
            'entries': entries, 'frames_per_entry': 600,
            'positive_count': len(entries),
            'negative_count': sum(len(row['missing_source_rejections'])
                                  for row in entries),
            'finalizer_sha256': sha(HERE / 'finalize.py'),
            'runtime_bound_diagnostic_only': True,
            'original_native_observed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    proof = run()
    path = HERE / 'offline' / 'all-finalizers-proof.json'
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'positive_count': proof['positive_count'],
                      'negative_count': proof['negative_count'],
                      'proof_sha256': sha(path)}))
