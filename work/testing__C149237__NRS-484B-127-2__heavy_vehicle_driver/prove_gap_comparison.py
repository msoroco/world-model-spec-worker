"""Exercise comparison audit positive and changed-fixed-width rejection."""
import hashlib
import json
import tempfile
from pathlib import Path
import shutil

from gap_comparison_audit import audit

ROOT=Path(__file__).resolve().parents[2]
SUFFIXES=('gap_below_500ft','gap_at_500ft','gap_above_500ft')
PATHS={s:ROOT/'.runtime-work'/('c149237-'+s+'-saved-v13')/'v0001/analysis'
       for s in SUFFIXES}
FILES=('config.json','result.json','analysis-report.json','road_context.json',
       'truck_history.jsonl','video_frames.jsonl')


def main():
    positive=audit(PATHS)
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c149237-gap-audit-') as temporary:
        changed=Path(temporary)/'changed';changed.mkdir()
        for name in FILES:shutil.copyfile(PATHS['gap_at_500ft']/name,changed/name)
        rows=[json.loads(line) for line in (changed/'truck_history.jsonl').read_text().splitlines()]
        for row in rows:row['ego']['overall_width_m']=2.3
        (changed/'truck_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report=json.loads((changed/'analysis-report.json').read_text())
        current=hashlib.sha256((changed/'truck_history.jsonl').read_bytes()).hexdigest()
        report['measurements']['minimum_sampled_body_gap_m']['sources']['truck_history.jsonl']=current
        (changed/'analysis-report.json').write_text(json.dumps(report)+'\n')
        negative=dict(PATHS,gap_at_500ft=changed)
        try:audit(negative)
        except ValueError as error:
            if 'Fixed comparison condition differs: widths_m' not in str(error):raise
        else:raise AssertionError('Changed fixed truck width was accepted')
        (changed/'truck_history.jsonl').unlink()
        try:audit(negative)
        except FileNotFoundError:pass
        else:raise AssertionError('Missing original truck history was accepted')
    print(json.dumps({'positive':positive,'negative_changed_fixed_width':'rejected',
                      'negative_missing_original_history':'rejected'},indent=2))


if __name__=='__main__':main()
