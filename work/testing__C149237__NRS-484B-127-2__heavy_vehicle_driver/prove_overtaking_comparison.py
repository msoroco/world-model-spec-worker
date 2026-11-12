"""Prove overtaking comparison rejects changed phase source and missing history."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from overtaking_comparison_audit import CASES, audit

ROOT = Path(__file__).resolve().parents[2]
PATHS = {s: ROOT/'.runtime-work'/('c149237-'+s+'-saved-v14')/'v0001/analysis' for s in CASES}
FILES = ('config.json', 'result.json', 'analysis-report.json', 'road_context.json',
         'truck_history.jsonl', 'video_frames.jsonl')


def main():
    positive = audit(PATHS)
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work', prefix='c149237-pass-audit-') as tmp:
        changed = Path(tmp)/'changed'
        changed.mkdir()
        for name in FILES:
            shutil.copyfile(PATHS['overtaking']/name, changed/name)
        rows = [json.loads(s) for s in (changed/'truck_history.jsonl').read_text().splitlines()]
        for row in rows:
            row['ego']['lane_id'] = -1
        (changed/'truck_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report = json.loads((changed/'analysis-report.json').read_text())
        checksum = hashlib.sha256((changed/'truck_history.jsonl').read_bytes()).hexdigest()
        report['measurements']['minimum_sampled_body_gap_m']['sources']['truck_history.jsonl'] = checksum
        (changed/'analysis-report.json').write_text(json.dumps(report)+'\n')
        negative = dict(PATHS, overtaking=changed)
        try:
            audit(negative)
        except ValueError as error:
            if 'phases differ' not in str(error):
                raise
        else:
            raise AssertionError('Changed passing lanes were accepted')
        (changed/'truck_history.jsonl').unlink()
        try:
            audit(negative)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Missing original truck history was accepted')
    print(json.dumps({'positive': positive, 'changed_passing_lanes': 'rejected',
                      'missing_original_history': 'rejected'}, indent=2))


if __name__ == '__main__':
    main()
