"""Retain exact independent saved comparison reports for all five pairs."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from audit_saved_comparison import audit

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(case):
    suffix = case.rsplit('__', 1)[1]
    version = 'v24' if suffix.startswith('freight_') else 'v18'
    return SCRATCH / f'saved-{suffix}-positive-{version}-output/v0001/analysis'


def main():
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    reports = []
    for item in plan['comparisons']:
        left, right = [source(case) for case in item['case_ids']]
        report = audit(item['comparison_id'], left, right, synthetic_fixture=True)
        name = item['comparison_id'].rsplit('__', 1)[1]
        target = PACKAGE / 'native-selected' / (name + '-saved-comparison.json')
        target.write_text(json.dumps(report, indent=2) + '\n')
        reports.append({'comparison_id': item['comparison_id'],
                        'report': str(target.relative_to(PACKAGE)),
                        'sha256': sha(target), 'source_kind': 'synthetic_cpu_fixture',
                        'physical_or_legal_acceptance': False})
    item = next(x for x in plan['comparisons'] if x['comparison_id'].endswith('__freight_load_comparison'))
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c150173-comparison-negative-') as temporary:
        negative = Path(temporary) / 'right'
        shutil.copytree(source(item['case_ids'][1]), negative)
        config_path = negative / 'config.json'
        config = json.loads(config_path.read_text())
        config['taxi_stop_x_m'] = 9.0
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        try:
            audit(item['comparison_id'], source(item['case_ids'][0]), negative,
                  synthetic_fixture=True)
        except ValueError as error:
            if 'Taxi comparison changed a fixed condition' not in str(error):
                raise
            log = 'Expected independent fixed-condition failure: ' + str(error) + '\n'
        else:
            raise ValueError('Changed fixed taxi stop unexpectedly passed comparison')
    log_path = PACKAGE / 'native-selected/saved-comparison-negative-fixed.log'
    log_path.write_text(log)
    summary = {'format': 'c150173-saved-comparison-cpu-v1',
        'assignment_id': PACKAGE.name, 'comparisons': reports,
        'negative_test': {'mutation': 'freight_load taxi_stop_x_m 5.5 -> 9.0',
            'expected_error': 'Taxi comparison changed a fixed condition',
            'log': str(log_path.relative_to(PACKAGE)), 'sha256': sha(log_path)},
        'original_native_observed': False, 'legal_verdict': None}
    output = PACKAGE / 'native-selected/saved-comparison-summary.json'
    output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'comparisons': len(reports), 'summary_sha256': sha(output)}))


if __name__ == '__main__':
    main()
