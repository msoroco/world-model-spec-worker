"""Check selected diagnostic pair isolation without claiming original coverage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / '.runtime-work/c143687-nov25a'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    observed = {}
    for suffix in ('posted_enter', 'posted_stop', 'posted_remain_trail'):
        path = SCRATCH / f'v2-compat-{suffix}/analysis-report.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('diagnostic_fixture') is not True or report.get('legal_verdict_claimed') is not False:
            raise ValueError('diagnostic comparison source status differs')
        value = report['measurements']['bicycle_roadway_use']['value']
        if (value.get('source_kind') != 'diagnostic_fixture_measurement' or
                value.get('case_id') != HERE.name + '__' + suffix or
                value.get('frames') != 900 or value.get('sign_posted_original_frames') != 900):
            raise ValueError('diagnostic case measurement incomplete')
        observed[value['case_id']] = {'value': value, 'report_sha256': sha(path)}
    receipts = []
    for comparison in plan['comparisons']:
        left, right = (observed[case_id] for case_id in comparison['case_ids'])
        a, b = left['value'], right['value']
        if a['site_sha256'] != b['site_sha256'] or a['designation_source'] != b['designation_source']:
            raise ValueError('fixed designation/sign/route site changed')
        if a['roadway_frames'] <= 0 or b['roadway_frames'] != 0 or b['trail_frames'] <= 0:
            raise ValueError('requested roadway/trail contrast missing')
        receipts.append({'comparison_id': comparison['comparison_id'],
                         'case_ids': comparison['case_ids'],
                         'fixed_site_sha256': a['site_sha256'],
                         'analysis_sha256': [left['report_sha256'], right['report_sha256']],
                         'roadway_frames': [a['roadway_frames'], b['roadway_frames']],
                         'source_kind': 'diagnostic_fixture_measurement',
                         'original_coverage_claimed': False,
                         'legal_assessment': 'unresolved'})
    output = {'format': 'c143687-diagnostic-comparison-isolation-v1',
              'assignment_id': HERE.name, 'receipts': receipts}
    (HERE / 'diagnostic-comparison-receipts.json').write_text(
        json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print('two fixed-site diagnostic bicycle comparisons passed')


if __name__ == '__main__':
    main()
