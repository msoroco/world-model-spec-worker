"""Exercise the proposed original-size saved path with explicit CPU mocks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prove_finalizer import attempt, invoke

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(case, candidate, dest):
    attempt(case, candidate, dest)
    receipt = json.loads((HERE / 'portable-receipts' / case / candidate / 'summary.json').read_text())
    fixture = REPO / receipt['fixture_runtime_relative']
    for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                 'driver_reference.mkv', 'raw.mkv'):
        shutil.copy2(fixture / name, dest / name)
    (dest / 'four-view-source.json').write_text(json.dumps({
        'format': 'synthetic_mock_original_size_path_only',
        'original_carla_pixels_verified': False}) + '\n')
    rows = [json.loads(line) for line in (dest / 'native_samples.jsonl').read_text().splitlines()]
    for row in rows:
        row['source_kind'] = 'original_native_observation'
    (dest / 'native_samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return receipt


def prove():
    rows = []
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111331-original-handoff-') as tmp:
        scratch = Path(tmp)
        for case in ('reference', 'contrast'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                dest = scratch / (case + '-' + candidate)
                receipt = prepare(case, candidate, dest)
                positive = invoke(dest)
                if positive.returncode:
                    raise ValueError('Original-format mock saved finalization failed: ' + positive.stdout[-900:])
                report = json.loads((dest / 'analysis-report.json').read_text())
                result = json.loads((dest / 'result.json').read_text())
                if (not report['original_source_review_pending'] or
                        report['signal_video_decode']['original_carla_pixels_verified'] or
                        result['accepted'] or result['provenance_kind'] != 'original_native_unreviewed'):
                    raise ValueError('Mock original-format result claimed acceptance or pixel proof')
                negative = scratch / (case + '-' + candidate + '-missing')
                prepare(case, candidate, negative)
                (negative / 'raw.mkv').unlink()
                failed = invoke(negative)
                if failed.returncode == 0 or 'Missing required source: raw.mkv' not in failed.stdout:
                    raise ValueError('Original-format missing-four-view negative accepted')
                retained = HERE / 'original-handoff-receipts' / case / candidate
                retained.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest / 'analysis-report.json', retained / 'analysis-report.json')
                shutil.copy2(dest / 'result.json', retained / 'result.json')
                (retained / 'negative-analysis.log').write_text(failed.stdout)
                rows.append({'case': case, 'candidate': candidate,
                             'manifest_sha256': receipt['manifest_sha256'],
                             'mock_native_sha256': sha(dest / 'native_samples.jsonl'),
                             'mock_reference_corner_sha256': sha(dest / 'reference_corner.mkv'),
                             'positive_report_sha256': sha(retained / 'analysis-report.json'),
                             'positive_result_sha256': sha(retained / 'result.json'),
                             'negative_log_sha256': sha(retained / 'negative-analysis.log'),
                             'missing_four_view_rejected': True,
                             'original_pixels_verified': False,
                             'native_executed': False})
    output = {'format': 'c111331-original-format-synthetic-handoff-v1',
              'rows': rows, 'positive_count': 8, 'negative_count': 8,
              'scope': 'synthetic source-kind mock for later original-size saved path; no Native execution or pixel review'}
    path = HERE / 'original-handoff-summary.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'summary_sha256': sha(path),
                      'positives': 8, 'negatives': 8}, sort_keys=True))


if __name__ == '__main__':
    prove()
