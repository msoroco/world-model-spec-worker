"""Exercise width comparison and reject changed counterpart/missing originals."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from width_comparison_audit import CASES,audit

ROOT=Path(__file__).resolve().parents[2]
PATHS={s:ROOT/'.runtime-work'/('c149237-'+s+'-saved-v16')/'v0001/analysis'
       for s in CASES}
FILES=('config.json','result.json','analysis-report.json','road_context.json',
       'truck_history.jsonl','video_frames.jsonl')


def main():
    positive=audit(PATHS)
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c149237-width-audit-') as tmp:
        changed=Path(tmp)/'changed';changed.mkdir()
        for name in FILES:shutil.copyfile(PATHS['ego_width_below_80in']/name,changed/name)
        rows=[json.loads(line) for line in (changed/'truck_history.jsonl').read_text().splitlines()]
        for row in rows:row['lead']['overall_width_m']=2.3
        (changed/'truck_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report=json.loads((changed/'analysis-report.json').read_text())
        report['measurements']['minimum_overall_width_m']['value']['lead']=2.3
        checksum=hashlib.sha256((changed/'truck_history.jsonl').read_bytes()).hexdigest()
        report['measurements']['minimum_overall_width_m']['sources']['truck_history.jsonl']=checksum
        (changed/'analysis-report.json').write_text(json.dumps(report)+'\n')
        negative=dict(PATHS,ego_width_below_80in=changed)
        try:audit(negative)
        except ValueError as error:
            if 'changed fixed counterpart width' not in str(error):raise
        else:raise AssertionError('Changed counterpart width was accepted')
        (changed/'truck_history.jsonl').unlink()
        try:audit(negative)
        except FileNotFoundError:pass
        else:raise AssertionError('Missing original truck history was accepted')
    print(json.dumps({'positive':positive,'changed_counterpart_width':'rejected',
                      'missing_original_history':'rejected'},indent=2))


if __name__=='__main__':main()
