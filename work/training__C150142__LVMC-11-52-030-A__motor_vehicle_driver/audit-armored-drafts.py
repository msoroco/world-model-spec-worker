"""Independent CPU draft audit for the four armored text-6 alternatives."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def construction(slug, candidate):
    path = ROOT / ('selected-primary' if candidate == 'primary'
                   else 'selected-fallbacks') / slug
    if candidate != 'primary':
        path /= candidate
    path /= 'construction.json'
    package = json.loads(path.read_text())
    files = {row['path']: row['content'] for row in package['files']}
    return path, package, files, json.loads(files['config.json'])


def audit(proofs=None):
    if proofs is None:
        proofs = [json.loads((ROOT / name).read_text()) for name in (
            'update043-armored-offline-matrix.json',
            'update043-armored-source-matrix.json',
            'update043-armored-saved-matrix.json')]
    offline, sources, saved = proofs
    if not offline['all_passed'] or len(offline['candidates']) != 16 or \
       sources['count'] != 16 or saved['count'] != 16:
        raise ValueError('Armored proof matrix incomplete')
    offline_index = {(r['case'], r['candidate']): r for r in offline['candidates']}
    source_index = {(r['case'], r['candidate']): r for r in sources['records']}
    saved_index = {(r['case'], r['candidate']): r for r in saved['records']}
    if any(len(index) != 16 for index in (offline_index, source_index, saved_index)):
        raise ValueError('Duplicate armored proof receipt')
    cases = {}
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            slug = 'armored_car_' + sign + '_' + activity
            manifest = json.loads((ROOT / ('execution-manifest-diagnostic-' +
                                            slug + '-draft.json')).read_text())
            entry = manifest['cases'][0]
            if entry['case_id'] != ROOT.name + '__' + slug or \
               len(entry['candidates']) != 3:
                raise ValueError('Armored exact manifest or fallbacks differ')
            configs = {}
            for candidate in CANDIDATES:
                key = (slug, candidate)
                path, package, files, config = construction(slug, candidate)
                declared = entry if candidate == 'primary' else next(
                    row for row in entry['candidates'] if row['id'] == candidate)
                if declared['construction_sha256'] != sha(path) or \
                   config['candidate_id'] != candidate or \
                   config['case_id'] != ROOT.name + '__' + slug or \
                   config['service_class'] != 'armored_car' or \
                   config['native_blueprint'] != 'vehicle.mercedes.sprinter' or \
                   config['armor_panel_blueprint'] != 'static.prop.box01' or \
                   config['armor_proxy_kind'] != 'attached_box_panels_v1' or \
                   config['sign_classes'] != (
                       ['armored_or_emergency'] if sign == 'signed' else []) or \
                   config['activity_request'] != (
                       'business_activity' if activity == 'business' else None) or \
                   config['requested_stationary_duration_s'] != 12 or \
                   config['capture_frames'] != 361 or \
                   'armored_proxy.spawn(' not in files['runner.py'] or \
                   'verify_readback(' not in files['finalize_selected.py'] or \
                   'armored_proxy.py' not in files:
                    raise ValueError('Armored executable construction differs: ' + str(key))
                if offline_index[key]['returncode'] != 0 or \
                   not all(source_index[key][field] for field in (
                       'positive_finalizer', 'missing_panel_source_rejected',
                       'wrong_panel_blueprint_rejected')) or \
                   saved_index[key]['construction_sha256'] != sha(path) or \
                   not saved_index[key]['four_source_decodes'] or \
                   saved_index[key]['frames'] != 361 or \
                   saved_index[key]['legal_armored_identity_verified']:
                    raise ValueError('Armored CPU proof differs: ' + str(key))
                configs[candidate] = config
            triggers = [configs[c]['risk_trigger'] for c in CANDIDATES[1:]]
            if len(set(triggers)) != 3 or any(t in ('', 'none') for t in triggers):
                raise ValueError('Armored fallback risk triggers not distinct')
            cases[slug] = configs
    for candidate in CANDIDATES:
        for sign in ('unsigned', 'signed'):
            business = cases['armored_car_' + sign + '_business'][candidate]
            absence = cases['armored_car_' + sign + '_no_business'][candidate]
            excluded = {'case_id', 'selected_case_id', 'supported_case_ids',
                        'activity_request'}
            if {k:v for k,v in business.items() if k not in excluded} != \
               {k:v for k,v in absence.items() if k not in excluded}:
                raise ValueError('Armored activity pair changed fixed construction')
        for activity in ('business', 'no_business'):
            unsigned = cases['armored_car_unsigned_' + activity][candidate]
            signed = cases['armored_car_signed_' + activity][candidate]
            excluded = {'case_id', 'selected_case_id', 'supported_case_ids',
                        'road_sha256', 'sign_classes'}
            if {k:v for k,v in unsigned.items() if k not in excluded} != \
               {k:v for k,v in signed.items() if k not in excluded}:
                raise ValueError('Armored sign pair changed fixed construction')
    return {'kind': 'independent_armored_draft_audit', 'cases': 4,
            'candidate_proofs': 16, 'activity_pairs': 8, 'sign_pairs': 8,
            'four_source_saved_processing': True,
            'legal_armored_identity_verified': False,
            'selected_delivery_proven': False}


if __name__ == '__main__':
    result = audit()
    target = ROOT / 'update043-armored-draft-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
