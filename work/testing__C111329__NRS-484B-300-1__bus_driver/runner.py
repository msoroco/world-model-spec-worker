"""Exact Native bus/device capture entrypoint; CPU check is source-gated."""
import argparse
import importlib
import json
import os
from pathlib import Path

from native_capture import capture
from package_spec import AID, CASES, case_id


def check(config):
    case = next((row for row in CASES if case_id(row[0]) == config.get('selected_case_id')), None)
    if case is None or config.get('case', {}).get('case_id') != config['selected_case_id']:
        raise ValueError('exact device case identity changed')
    if (config['case'].get('device_aspect'), config['case'].get('bus_control_policy'),
            config['case'].get('police_direction')) != case[1:4]:
        raise ValueError('device/controller source request changed')
    if config.get('candidate_id') not in ('primary', 'fallback1'):
        raise ValueError('unknown Native candidate')
    return {'case_id': config['selected_case_id'], 'source_gate': 'reviewed original site required',
            'physical_acceptance': False, 'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('config.json'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--adapter-module')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    checked = check(config)
    if args.check:
        print(json.dumps(checked))
        return
    site = args.site or os.environ.get('C111329_REVIEWED_SITE')
    adapter_module = args.adapter_module or os.environ.get('C111329_NATIVE_ADAPTER_MODULE')
    if not site or not adapter_module or args.output_dir is None:
        raise ValueError('reviewed original site, Native adapter and output directory required')
    module = importlib.import_module(adapter_module)
    adapter = module.open_adapter()
    case_name = config['selected_case_id'].removeprefix(AID + '__')
    result = capture(adapter, Path(site), case_name, args.output_dir,
                     config['candidate_id'], config['control_profile'])
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
