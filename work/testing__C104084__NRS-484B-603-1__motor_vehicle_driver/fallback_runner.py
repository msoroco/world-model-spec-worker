"""Local Native entrypoint for the selected C104084 hill crest probes.

The operator supplies a reviewed site packet and a fresh external attempt path.
The source packet binds the authored crest map and prescribed speed-limit record;
all observed motion and pixels come from the local Native CARLA capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from canonical_crest import publish
from native_crest_runner import capture
from saved_crest_audit import ASSIGNMENT, PROFILES


def reviewed_site(path, case_id):
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding='utf-8'))
    if site.get('format') != 'c104084-reviewed-crest-site-v1' or site.get('case_id') != case_id:
        raise ValueError('exact reviewed crest site case required')
    if site.get('review_status') != 'reviewed_original_source':
        raise ValueError('independent original source review required')
    files = {}
    for name in ('map', 'limit'):
        binding = site.get(name)
        if not isinstance(binding, dict) or binding.get('origin') != 'reviewed_original':
            raise ValueError(name + ' reviewed original source required')
        relative = binding.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError(name + ' relative source path required')
        source = (path.parent / relative).resolve()
        if (not source.is_relative_to(path.parent) or not source.is_file()
                or source.is_symlink()):
            raise ValueError(name + ' reviewed original source missing')
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if binding.get('sha256') != actual:
            raise ValueError(name + ' reviewed original source hash differs')
        files[name] = source
    limit = json.loads(files['limit'].read_text(encoding='utf-8'))
    if (limit.get('road_id') != 603 or limit.get('source_kind') != 'reviewed_original_limit'
            or limit.get('prescribed_limit_mps') != site.get('prescribed_limit_mps')):
        raise ValueError('reviewed prescribed limit does not bind this crest road')
    return {'site': site, 'map_path': files['map'],
            'map_sha256': site['map']['sha256'],
            'limit_path': files['limit'],
            'limit_mps': limit['prescribed_limit_mps'],
            'limit_source_ref': f'{files["limit"].name}:{site["limit"]["sha256"]}'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case')
    parser.add_argument('--site')
    parser.add_argument('--attempt')
    parser.add_argument('--output-dir')
    parser.add_argument('--scratch-root')
    parser.add_argument('--capture-ref')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    config_path = Path(__file__).resolve().with_name('config.json')
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
    selected_case = args.case or config.get('selected_case_id')
    if selected_case not in {ASSIGNMENT + '__' + profile for profile in PROFILES}:
        raise ValueError('selected exact crest case required')
    if config and (config.get('assignment_id') != ASSIGNMENT or
                   config.get('selected_case_id') != selected_case or
                   config.get('duration_s') != 45 or config.get('rate_hz') != 20):
        raise ValueError('exact materialized crest config differs')
    camera_height_m = config.get('camera_height_m', 2.4)
    if (type(camera_height_m) not in (int, float) or
            not 2.0 <= camera_height_m <= 3.0):
        raise ValueError('reviewed camera mount height must be 2.0 to 3.0 metres')
    site_path = args.site
    if not site_path and not args.check:
        site_root = os.environ.get('C104084_SITE_ROOT')
        if not site_root:
            raise ValueError('C104084_SITE_ROOT reviewed site directory required')
        site_path = str(Path(site_root) / (selected_case.split('__')[-1] + '.json'))
    selected = reviewed_site(site_path, selected_case) if site_path else None
    if args.check:
        print(json.dumps({'case_id': selected_case, 'source_checked': bool(selected),
                          'site_sha256': hashlib.sha256(Path(site_path).read_bytes()).hexdigest()
                          if site_path else None}))
        return 0
    destination = args.attempt or args.output_dir
    if not destination:
        raise ValueError('fresh original Native attempt directory required')
    scratch_root = args.scratch_root or os.environ.get('C104084_SCRATCH_ROOT')
    if not scratch_root:
        raise ValueError('C104084_SCRATCH_ROOT under .runtime-work required')
    scratch_root = Path(scratch_root).resolve()
    if '.runtime-work' not in scratch_root.parts:
        raise ValueError('capture scratch must be under .runtime-work')
    scratch_root.mkdir(parents=True, exist_ok=True)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix='c104084-attempt-') as temporary:
        bundle = Path(temporary) / 'bundle'
        pipeline = Path(temporary) / 'pipeline'
        receipt = capture(client, carla, map_path=selected['map_path'],
            map_sha256=selected['map_sha256'], case_id=selected_case,
            destination=bundle, limit_mps=selected['limit_mps'],
            limit_source_ref=selected['limit_source_ref'],
            limit_path=selected['limit_path'],
            capture_ref=args.capture_ref or uuid.uuid4().hex,
            scratch_root=scratch_root, pipeline_destination=pipeline,
            camera_height_m=camera_height_m)
        publish(bundle, destination, selected_case, pipeline=pipeline)
    print(json.dumps({'case_id': receipt['case_id'],
                      'source_manifest_sha256': receipt['source_manifest_sha256'],
                      'physical_completion': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
