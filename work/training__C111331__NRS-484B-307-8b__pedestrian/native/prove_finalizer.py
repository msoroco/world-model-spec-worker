"""Exercise saved finalization and original-source rejection on CPU rows."""

import copy
import json
import os
from pathlib import Path
import tempfile

from finalize import finalize, measure
from native_red import CAMERAS, CONDITIONS, plan, sha
from prove_source_join import fixture

HERE = Path(__file__).resolve().parent


def write_rows(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item) + '\n' for item in items))


def reject(action, expected):
    try:
        action()
    except (ValueError, KeyError) as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return
    raise AssertionError('Expected rejection: ' + expected)


def main():
    scratch = Path(os.environ['TMPDIR'])
    if scratch.name != '.runtime-work':
        raise ValueError('Scratch must remain under .runtime-work')
    checks = []
    with tempfile.TemporaryDirectory(prefix='c111331-finalizer-', dir=scratch) as temp:
        for condition in CONDITIONS:
            root = Path(temp) / condition
            root.mkdir()
            construction = json.loads((HERE / 'native-drafts' / condition /
                                       'primary/construction.json').read_text())
            config = json.loads(next(item['content'] for item in construction['files']
                                     if item['path'] == 'config.json'))
            (root / 'config.json').write_text(json.dumps(config) + '\n')
            samples, mapping, cameras = fixture(config)
            trace = [{'frame': row['native_frame'], 'time_s': row['time_s'],
                      'position_m': [8.0, 5.0, 0.5], 'heading_deg': -90.0,
                      'red_entry_source': {k: v for k, v in row.items()
                                           if k != 'source_rgb_sha256'}} for row in samples]
            evidence = [{'original_frame': row['native_frame'],
                         'recording_time_s': row['time_s'],
                         'actor_id': row['walker_id']} for row in samples]
            for name, rows in [('red-entry-original.jsonl', samples),
                               ('video_frames.jsonl', mapping),
                               ('camera-sources.jsonl', cameras),
                               ('trace.jsonl', trace),
                               ('capture/evidence.jsonl', evidence)]:
                write_rows(root / name, rows)
            for name, _, _, _ in CAMERAS:
                (root / (name + '.mkv')).write_bytes(b'synthetic-placeholder')
            report = finalize(root, root / 'analysis-report.json')
            result = json.loads((root / 'result.json').read_text())
            joined = report['measurements']['intersection_entry_scope']['value']
            assert joined['trace_evidence_join_passed'] is True
            assert result['case_id'] == config['case_id']
            assert result['provenance_kind'] == 'synthetic_cpu' and not result['accepted']
            assert report['legal_verdict'] is None
            (root / 'result.json').unlink()
            write_rows(root / 'trace.jsonl', trace[:-1])
            reject(lambda: measure(root), 'Incomplete original pedestrian capture streams')
            write_rows(root / 'trace.jsonl', trace)
            changed = copy.deepcopy(evidence)
            changed[120]['actor_id'] += 1
            write_rows(root / 'capture/evidence.jsonl', changed)
            reject(lambda: measure(root), 'Original pedestrian capture identity differs')
            checks.append(config['case_id'])
    receipt = {'format': 'c111331-finalizer-source-cpu-proof-v1',
               'case_ids': checks, 'positive_checks': len(checks),
               'negative_checks': len(checks) * 2,
               'finalizer_sha256': sha(HERE / 'finalize.py'),
               'source_join_sha256': sha(HERE / 'source_join.py'),
               'fixture_is_synthetic': True, 'native_executed': False,
               'physical_pixels_reviewed': False, 'legal_verdict_claimed': False}
    path = HERE.parent / 'native-red-finalizer-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'positive_checks': len(checks),
                      'negative_checks': len(checks) * 2,
                      'receipt_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
