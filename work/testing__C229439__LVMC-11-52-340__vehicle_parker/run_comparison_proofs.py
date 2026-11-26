"""Exercise all four controlled comparisons and a fixed-condition mutation."""

import hashlib
import json
from pathlib import Path

from comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229439-comparison-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    report_dir = SCRATCH / 'reports'
    report_dir.mkdir(exist_ok=True)
    for row in plan['cases']:
        suffix = row['case_id'].rsplit('__', 1)[-1]
        source = ROOT / ('audit-' + suffix + '-positive.log')
        report = json.loads(source.read_text())
        (report_dir / (suffix + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    for comparison in plan['comparisons']:
        cid = comparison['comparison_id']
        result = audit(cid, report_dir, synthetic_fixture=True)
        if result.get('passed') is not True:
            raise ValueError('controlled comparison failed: ' + cid)
        positive = ROOT / ('comparison-' + cid + '-positive.log')
        positive.write_text(json.dumps(result, indent=2) + '\n')
        negative_dir = SCRATCH / (cid + '-negative')
        negative_dir.mkdir(exist_ok=True)
        for path in report_dir.glob('*.json'):
            (negative_dir / path.name).write_bytes(path.read_bytes())
        changed = negative_dir / (comparison['case_ids'][1].rsplit('__', 1)[-1] + '.json')
        report = json.loads(changed.read_text())
        report['duration_s'] += 1
        changed.write_text(json.dumps(report, indent=2) + '\n')
        negative = ROOT / ('comparison-' + cid + '-negative.log')
        try:
            audit(cid, negative_dir, synthetic_fixture=True)
        except ValueError as error:
            negative.write_text(str(error) + '\n')
        else:
            raise ValueError('comparison failed to reject fixed-condition mutation: ' + cid)
        if 'changed fixed conditions' not in negative.read_text():
            raise ValueError('wrong comparison negative rejection: ' + cid)
        print(cid, 'passed', sha(positive), sha(negative), flush=True)


if __name__ == '__main__':
    run()
