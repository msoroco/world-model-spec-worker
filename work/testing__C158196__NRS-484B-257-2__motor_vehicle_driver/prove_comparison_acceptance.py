"""Full-length synthetic source proof for each independent pair comparison."""

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from comparison_audit import PAIRS, audit
from delivery_audit import audit_delivery


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=PAIRS, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    raw_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not raw_root:
        raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work is required')
    output = Path(raw_root).resolve()
    private = (REPO / '.runtime-work').resolve()
    if output != private and private not in output.parents:
        raise ValueError('Output root outside .runtime-work')
    first_suffix, second_suffix = PAIRS[args.comparison]
    first, second = output / first_suffix, output / second_suffix
    if args.mode == 'positive':
        source_audits = [audit_delivery(source, PACKAGE, PREFIX + suffix,
                                        diagnostic_fixture=True)
                         for source, suffix in ((first, first_suffix), (second, second_suffix))]
        receipt = audit(args.comparison, first, second)
        receipt['source_audits'] = [dict(case_id=item['case_id'],
                                         frame_map_sha256=item['frame_map_sha256'],
                                         software_audit_passed=item['software_audit_passed'])
                                    for item in source_audits]
        print(json.dumps(receipt, indent=2))
        return
    with tempfile.TemporaryDirectory(dir=output, prefix='changed-fixed-camera-') as temporary:
        changed = Path(temporary) / 'changed'
        shutil.copytree(second, changed, copy_function=os.link)
        config_path = changed / 'config.json'
        config = json.loads(config_path.read_text())
        config['cameras'][0]['width'] += 1
        config_path.unlink()
        config_path.write_text(json.dumps(config) + '\n')
        audit(args.comparison, first, changed)
        raise AssertionError('Changed fixed camera unexpectedly accepted')


if __name__ == '__main__':
    main()
