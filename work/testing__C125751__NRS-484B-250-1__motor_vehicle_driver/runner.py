"""Exact C125751 Native entrypoint. Reviewed source bytes are mandatory."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from case_protocol import ASSIGNMENT, FIXED, validate_case
from source_bindings import bind_sources, prepare_capture_spec


def main():
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-spec', type=Path, default=folder / 'case-spec.json')
    parser.add_argument('--sources', type=Path,
                        default=Path(os.environ.get('C125751_REVIEWED_SOURCES',
                                                    str(folder / 'reviewed-sources'))))
    parser.add_argument('--camera-plan', type=Path, default=folder / 'camera-plan.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    spec = json.loads(args.case_spec.read_text())
    suffix = spec['case_id'].removeprefix(ASSIGNMENT + '__')
    if args.check:
        validate_case(spec, suffix, require_source=False)
        bound = all(spec.get(key) for key in FIXED[6:])
        packet = bind_sources(spec, suffix, args.sources, args.camera_plan) if bound else None
        print(json.dumps({'case_id': spec['case_id'], 'source_bound': bound,
                          'source_binding': 'reviewed_original' if bound else
                                            'required_before_Native_capture',
                          'crossing_id': packet['crossing_id'] if packet else None,
                          'native_started': False}))
    elif args.output_dir:
        spec = prepare_capture_spec(spec, suffix, args.sources, args.camera_plan,
                                    {'ego': os.environ.get('C125751_EGO_BLUEPRINT'),
                                     'other': os.environ.get('C125751_OTHER_BLUEPRINT')})
        from native_capture import run_native
        run_native(spec, suffix, args.sources, args.camera_plan,
                   args.output_dir, args.host, args.port)
    else:
        parser.error('use --check or --output-dir')


if __name__ == '__main__':
    main()
