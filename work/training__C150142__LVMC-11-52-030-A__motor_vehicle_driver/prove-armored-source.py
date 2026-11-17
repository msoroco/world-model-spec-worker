"""Prove saved finalizers from source-shaped armored-proxy rows and negatives."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def readback(attempt):
    config = json.loads((attempt / 'config.json').read_text())
    first = json.loads((attempt / 'native-raw-actors.jsonl').read_text().splitlines()[0])
    proxy = helper('armored_proxy', 'native/armored_proxy.py')
    return {'source_kind': 'synthetic_native_sample',
            'base_actor_id': first['actor_id'],
            'base_blueprint': config['native_blueprint'],
            'panels': [{'name': name, 'actor_id': 100 + index,
                        'blueprint': proxy.PANEL_BLUEPRINT,
                        'relative_location_m': list(location),
                        'relative_rotation_deg': list(rotation)}
                       for index, (name, location, rotation) in enumerate(proxy.PANELS)],
            'legal_armored_identity_verified': False}


def write_readback(attempt, value):
    (attempt / 'native-armor-proxy-readback.json').write_text(
        json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    records = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            slug = 'armored_car_' + sign + '_' + activity
            emergency_slug = 'emergency-' + ('signed-' if sign == 'signed' else '') + (
                'business' if activity == 'business' else 'no-business')
            helper_source = helper('source_' + slug,
                                   'prove-' + emergency_slug + '-source.py')
            manifest = ROOT / ('execution-manifest-diagnostic-' + slug + '-draft.json')
            case = ROOT.name + '__' + slug
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                                 prefix='c150142-armored-source-') as temp:
                    parent = Path(temp)
                    positive = parent / 'positive'
                    helper_source.materialize(manifest, case, positive, candidate)
                    helper_source.source_rows(positive)
                    value = readback(positive)
                    write_readback(positive, value)
                    result = helper_source.run(positive)
                    if result.returncode:
                        raise AssertionError(slug + '/' + candidate + ': ' +
                                             result.stderr[-2000:])
                    analysis = json.loads((positive / 'analysis-report.json').read_text())
                    observed = analysis['measurements']['signed_curb_observation']['value']
                    if observed['red_curb_stationary_duration_s'] != 12 or \
                       observed['sign_present'] != (sign == 'signed') or \
                       [r['name'] for r in observed['recorded_activity_events']] != (
                           ['business_activity'] if activity == 'business' else []) or \
                       observed['necessary_business_established'] is not None or \
                       observed['legal_verdict'] is not None:
                        raise AssertionError('Armored source observation differs: ' + slug)
                    missing = parent / 'missing-panels'
                    helper_source.materialize(manifest, case, missing, candidate)
                    helper_source.source_rows(missing)
                    rejected = helper_source.run(missing)
                    if rejected.returncode == 0 or \
                       'Missing required source: native-armor-proxy-readback.json' not in rejected.stderr:
                        raise AssertionError('Missing armor source accepted: ' + slug)
                    damaged = parent / 'damaged-panel'
                    helper_source.materialize(manifest, case, damaged, candidate)
                    helper_source.source_rows(damaged)
                    mutation = readback(damaged)
                    mutation['panels'][2]['blueprint'] = 'static.prop.unknown'
                    write_readback(damaged, mutation)
                    rejected = helper_source.run(damaged)
                    if rejected.returncode == 0 or \
                       'Armored proxy panel readback differs' not in rejected.stderr:
                        raise AssertionError('Damaged armor source accepted: ' + slug)
                    records.append({'case': slug, 'candidate': candidate,
                                    'positive_finalizer': True,
                                    'missing_panel_source_rejected': True,
                                    'wrong_panel_blueprint_rejected': True,
                                    'native_executed': False,
                                    'legal_armored_identity_verified': False})
    target = ROOT / 'update043-armored-source-matrix.json'
    target.write_text(json.dumps({'kind': 'source_shaped_diagnostic',
                                  'count': len(records), 'records': records},
                                 indent=2, allow_nan=False) + '\n')
    print(json.dumps({'count': len(records), 'all_passed': True,
                      'receipt': str(target.relative_to(REPO))}))


if __name__ == '__main__':
    main()
