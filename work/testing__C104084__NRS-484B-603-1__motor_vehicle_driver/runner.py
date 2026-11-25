"""Local Native entrypoint for the selected C104084 hill crest probes.

The operator supplies a reviewed site packet and a fresh external attempt path.
The source packet binds the authored crest map and prescribed speed-limit record;
all observed motion and pixels come from the local Native CARLA capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

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
            'limit_mps': limit['prescribed_limit_mps'],
            'limit_source_ref': f'{files["limit"].name}:{site["limit"]["sha256"]}'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--site', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--scratch-root', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if args.case not in {ASSIGNMENT + '__' + profile for profile in PROFILES}:
        raise ValueError('selected exact crest case required')
    selected = reviewed_site(args.site, args.case)
    if args.check:
        print(json.dumps({'case_id': args.case, 'site_sha256':
            hashlib.sha256(Path(args.site).read_bytes()).hexdigest(),
            'map_sha256': selected['map_sha256'],
            'limit_source_ref': selected['limit_source_ref']}))
        return 0
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    receipt = capture(client, carla, map_path=selected['map_path'],
        map_sha256=selected['map_sha256'], case_id=args.case,
        destination=args.attempt, limit_mps=selected['limit_mps'],
        limit_source_ref=selected['limit_source_ref'],
        capture_ref=hashlib.sha256(Path(args.site).read_bytes()).hexdigest(),
        scratch_root=args.scratch_root)
    print(json.dumps({'case_id': receipt['case_id'],
                      'source_manifest_sha256': receipt['source_manifest_sha256'],
                      'physical_completion': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
