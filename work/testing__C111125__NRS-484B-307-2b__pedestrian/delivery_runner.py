"""Exact-case Native dispatch with reviewed pedestrian operator adapter.

The site packet binds map/head/device source bytes and the site-specific camera
and device reader adapter. The adapter owns world settings and restoration.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from native_capture import ASSIGNMENT
from owned_runner import capture_reviewed, seal_after_restoration
from pedestrian_control import ENTER_CASES, WAIT_CASES


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'scene.json').read_text())
    case = config.get('selected_case_id')
    suffix = case.removeprefix(ASSIGNMENT + '__') if isinstance(case, str) else None
    if (suffix not in ENTER_CASES | WAIT_CASES or case != ASSIGNMENT + '__' + suffix or
            config.get('case') != scene or scene.get('case_id') != case):
        raise ValueError('exact pedestrian delivery case identity mismatch')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('20 Hz, 45 second pedestrian capture required')
    if scene.get('diagnostic_only') is not False:
        raise ValueError('selected delivery construction cannot be diagnostic')
    if set(config.get('source_packets', [])):
        raise ValueError('site-specific original packets must arrive at Native dispatch')
    return config


def run(root, host, port):
    root = Path(root).resolve()
    config = check(root)
    site_var = os.environ.get('SCENARIO_REVIEWED_SITE_PACKET')
    adapter_var = os.environ.get('SCENARIO_PEDESTRIAN_OPERATOR_ADAPTER')
    if not site_var or not adapter_var:
        raise ValueError('reviewed site and pedestrian operator adapter sources required')
    site_path = Path(site_var).resolve(strict=True)
    site = json.loads(site_path.read_text())
    adapter_path = Path(adapter_var).resolve(strict=True)
    if (site.get('operator_adapter_source') !=
            {'path': str(adapter_path), 'sha256': _sha(adapter_path)}):
        raise ValueError('reviewed pedestrian operator adapter source mismatch')
    spec = importlib.util.spec_from_file_location('reviewed_pedestrian_operator_adapter',
                                                  adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed pedestrian operator adapter unavailable')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    session = adapter.create_session(host, int(port), config, site)
    restoration = None
    try:
        capture_reviewed(session, site_path, config['selected_case_id'], root)
    except Exception as error:
        (root / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['selected_case_id'], 'errors': [str(error)],
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        raise
    finally:
        restoration = session.restore()
    seal_after_restoration(root, restoration)
    return {'case_id': config['selected_case_id'], 'capture_sealed': True,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', default='.')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({'case_id': check(args.output_dir)['selected_case_id'],
                          'offline_precheck': 'passed'}))
        return
    if args.host is None or args.port is None:
        raise ValueError('original CARLA host and port required')
    print(json.dumps(run(args.output_dir, args.host, args.port)))


if __name__ == '__main__':
    main()
