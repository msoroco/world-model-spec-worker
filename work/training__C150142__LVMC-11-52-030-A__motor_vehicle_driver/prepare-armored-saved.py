"""Materialize one synthetic Native armored-proxy attempt with four cameras."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


SOURCE = module('armored_source', 'prove-armored-source.py')
GRAPH = module('armored_graph', 'build-armored-native-diagnostic.py')


def prepare(slug, candidate, attempt, manifest_override=None):
    if slug not in {'armored_car_' + sign + '_' + activity
                    for sign in ('unsigned', 'signed')
                    for activity in ('business', 'no_business')} or \
       candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown armored case or candidate')
    attempt = Path(attempt).resolve()
    if REPO / '.runtime-work' not in attempt.parents or attempt.exists():
        raise ValueError('Use fresh ignored diagnostic directory')
    sign = 'signed' if '_signed_' in slug else 'unsigned'
    activity = 'no_business' if slug.endswith('_no_business') else 'business'
    emergency_slug = 'emergency-' + ('signed-' if sign == 'signed' else '') + (
        'business' if activity == 'business' else 'no-business')
    helper = module('emergency_source', 'prove-' + emergency_slug + '-source.py')
    manifest = (Path(manifest_override).resolve() if manifest_override else
                ROOT / ('execution-manifest-diagnostic-' + slug + '-draft.json'))
    helper.materialize(manifest, ROOT.name + '__' + slug, attempt, candidate)
    helper.source_rows(attempt)
    SOURCE.write_readback(attempt, SOURCE.readback(attempt))
    graph = GRAPH.build(attempt)
    media_from = REPO / '.runtime-work' / (
        'c150142-' + emergency_slug + '-' + candidate + '-native-v1')
    for view in VIEWS:
        source = media_from / (view + '.mkv')
        if not source.is_file():
            raise ValueError('Missing four-camera neutral diagnostic source: ' + str(source))
        shutil.copy2(source, attempt / source.name)
    return {'case_id': ROOT.name + '__' + slug, 'candidate': candidate,
            'source_kind': 'synthetic_native_sample', 'graph': graph,
            'four_source_cameras': list(VIEWS),
            'armored_visual_proxy_only': True, 'native_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest')
    args = parser.parse_args()
    print(json.dumps(prepare(args.slug, args.candidate, args.attempt,
                             args.manifest), sort_keys=True))
