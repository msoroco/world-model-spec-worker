"""CPU proof of a source-bound fallback2 decision, with tamper negatives."""
import json
from pathlib import Path
import tempfile

from fallback_trigger import digest, evaluate
from prove_saved_source_analysis import sample, write_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE.parent / 'fallback-trigger-proof.json'
NAMES = ('native-pedestrian-frames.jsonl', 'video_frames.jsonl', 'road-boundary.json')


def hashes(path):
    return {name: digest(path / name) for name in NAMES}


def reject(fn, reason):
    try:
        fn()
    except ValueError:
        return reason
    raise AssertionError('Negative accepted: ' + reason)


def main():
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    negatives = []
    with tempfile.TemporaryDirectory(prefix='c228133-path-trigger-', dir=scratch) as temp:
        temp = Path(temp)
        stable = temp / 'stable'
        sample(stable, False)
        stable_hashes = hashes(stable)
        stable_result = evaluate(stable, stable_hashes, 1.2, diagnostic=True)
        assert stable_result['fallback2_triggered'] is False
        stepped = temp / 'stepped'
        sample(stepped, False)
        path = stepped / NAMES[0]
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[90]['footprint_roadward_y_m'] = .3
        write_rows(path, rows)
        stepped_hashes = hashes(stepped)
        stepped_result = evaluate(stepped, stepped_hashes, 1.2, diagnostic=True)
        assert stepped_result['unstable_step_frames'] == [90, 91]
        negatives.append(reject(lambda: evaluate(stepped, stable_hashes, 1.2, diagnostic=True), 'changed_source_hash'))
        negatives.append(reject(lambda: evaluate(stepped, stepped_hashes, 1.2), 'synthetic_claimed_as_native'))
        rows[90]['native_frame'] += 1
        write_rows(path, rows)
        negatives.append(reject(lambda: evaluate(stepped, hashes(stepped), 1.2, diagnostic=True), 'changed_frame_join'))
        rows.pop()
        write_rows(path, rows)
        negatives.append(reject(lambda: evaluate(stepped, hashes(stepped), 1.2, diagnostic=True), 'short_window'))
        negatives.append(reject(lambda: evaluate(stable, stable_hashes, 0, diagnostic=True), 'invalid_requested_speed'))
    result = {'format': 'c228133-fallback2-source-proof-v1',
              'trigger_source_sha256': digest(HERE / 'fallback_trigger.py'),
              'stable': {'source_hashes': stable_hashes,
                         'fallback2_triggered': stable_result['fallback2_triggered']},
              'unstable': {'source_hashes': stepped_hashes,
                           'unstable_step_frames': stepped_result['unstable_step_frames'],
                           'fallback2_triggered': stepped_result['fallback2_triggered']},
              'negative_rejections': negatives, 'frames': 600, 'rate_hz': 20,
              'synthetic_diagnostic': True, 'original_native_observed': False,
              'selection_or_legal_verdict': None}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': digest(OUT), 'negatives': negatives,
                      'fallback2_triggered': stepped_result['fallback2_triggered']}))


if __name__ == '__main__':
    main()
