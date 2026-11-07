"""Independent scope and hash audit of synthetic original-format handoff."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    summary = json.loads((HERE / 'original-handoff-summary.json').read_text())
    manifest = sha(HERE / 'package-manifest.json')
    if len(summary['rows']) != 8 or summary['positive_count'] != 8 or summary['negative_count'] != 8:
        raise ValueError('Original-format mock handoff count differs')
    seen = set()
    for row in summary['rows']:
        case, candidate = row['case'], row['candidate']
        if (case, candidate) in seen or row['manifest_sha256'] != manifest:
            raise ValueError('Original-format mock identity or manifest differs')
        seen.add((case, candidate))
        folder = HERE / 'original-handoff-receipts' / case / candidate
        report = json.loads((folder / 'analysis-report.json').read_text())
        result = json.loads((folder / 'result.json').read_text())
        if (row['positive_report_sha256'] != sha(folder / 'analysis-report.json') or
                row['positive_result_sha256'] != sha(folder / 'result.json') or
                row['negative_log_sha256'] != sha(folder / 'negative-analysis.log')):
            raise ValueError('Original-format mock receipt hash differs')
        if (not report['original_source_review_pending'] or
                report['signal_video_decode']['source_kind'] != 'original_size_unreviewed' or
                report['signal_video_decode']['original_carla_pixels_verified'] or
                result['accepted'] or result['provenance_kind'] != 'original_native_unreviewed' or
                'Missing required source: raw.mkv' not in (folder / 'negative-analysis.log').read_text()):
            raise ValueError('Original-format mock scope or negative differs')
        if result['case_id'] != report['case_id'] or not result['case_id'].endswith('__' + case):
            raise ValueError('Original-format mock case identity differs')
    print(json.dumps({'passed': True, 'positives': len(seen), 'negatives': len(seen),
                      'summary_sha256': sha(HERE / 'original-handoff-summary.json')}, sort_keys=True))


if __name__ == '__main__':
    audit()
