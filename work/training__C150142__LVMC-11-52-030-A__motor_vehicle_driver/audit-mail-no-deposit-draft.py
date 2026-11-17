"""Independently bind adjacent-mail fallbacks and source/saved CPU receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + '__mail_adjacent_no_deposit'
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest=None, saved=None, configurations=None):
    manifest = manifest or json.loads((ROOT / 'execution-manifest-diagnostic-mail-adjacent-no-deposit-draft.json').read_text())
    saved = saved or json.loads((ROOT / 'update042-mail-no-deposit-saved-matrix.json').read_text())
    if len(manifest['cases']) != 1 or manifest['cases'][0]['case_id'] != CASE:
        raise ValueError('Exact adjacent-mail manifest differs')
    entry = manifest['cases'][0]
    if [row['id'] for row in entry['candidates']] != list(CANDIDATES[1:]) or \
            entry['kind'] != 'delivery' or entry['candidate_risk']['status'] != 'physical':
        raise ValueError('Adjacent-mail fallback plan differs')
    configurations = configurations or {}
    configs, files = {}, {}
    for candidate in CANDIDATES:
        row = entry if candidate == 'primary' else next(
            item for item in entry['candidates'] if item['id'] == candidate)
        construction = ROOT / row['construction']
        if digest(construction) != row['construction_sha256']:
            raise ValueError('Adjacent-mail construction hash differs')
        package = json.loads(construction.read_text())
        payload = {item['path']: item['content'] for item in package['files']}
        config = configurations.get(candidate) or json.loads(payload['config.json'])
        if package['case_id'] != CASE or config['case_id'] != CASE or \
                config['candidate_id'] != candidate or \
                config['service_class'] != 'ordinary' or \
                config['native_blueprint'] != 'vehicle.tesla.model3' or \
                config['sign_classes'] != [] or \
                config['activity_request'] is not None or \
                config['requested_stationary_duration_s'] != 12 or \
                config['capture_frames'] != 361 or \
                digest_from_text(payload['red-curb-road.xodr']) != config['road_sha256']:
            raise ValueError('Adjacent-mail fixed conditions differ')
        configs[candidate], files[candidate] = config, payload
        offline = json.loads((ROOT / f'update042-mail-no-deposit-{candidate}-offline.log').read_text())
        proof = json.loads((ROOT / f'update042-mail-no-deposit-{candidate}-source-proof.json').read_text())
        if offline['offline_passed'] is not True or \
                proof['case_id'] != CASE or proof['candidate_id'] != candidate or \
                not all(proof[key] is True for key in ('empty_worker_and_parcel_inventories_derived',
                    'missing_parcel_source_rejected','unexpected_worker_rejected','unexpected_parcel_rejected')) or \
                proof['actual_mail_absence_established'] or proof['original_native_observed']:
            raise ValueError('Adjacent-mail offline or negative proof missing')
    baseline = configs['primary']
    for candidate in CANDIDATES[1:]:
        altered = {key for key in baseline if baseline[key] != configs[candidate].get(key)}
        if not altered <= {'candidate_id','risk_trigger','tracks_sha256',
                           'requested_target_x_m','camera_policy'}:
            raise ValueError('Adjacent-mail fallback changed fixed conditions')
        for name in ('red-curb-road.xodr','runner.py','finalize_selected.py',
                     'mail_absence.py','measure_exceptions.py','assignment-source.json'):
            if files[candidate][name] != files['primary'][name]:
                raise ValueError('Adjacent-mail fallback changed fixed source: '+name)
    if [(configs[c]['requested_target_x_m'],configs[c]['camera_policy']) for c in CANDIDATES] != [
            (40,'standard'),(38,'standard'),(40,'elevated_overview'),(42,'standard')]:
        raise ValueError('Adjacent-mail fallback mechanisms differ')
    rows = {row['candidate']: row for row in saved['candidates']}
    if set(rows) != set(CANDIDATES):
        raise ValueError('Adjacent-mail terminal candidate missing')
    for candidate in CANDIDATES:
        if rows[candidate]['construction_sha256'] != (
                entry if candidate == 'primary' else next(
                    item for item in entry['candidates'] if item['id']==candidate))['construction_sha256'] or \
                rows[candidate]['frames'] != 361 or \
                rows[candidate]['four_source_decodes'] is not True or \
                rows[candidate]['full_final_decode'] is not True or \
                rows[candidate]['actual_mail_absence_established'] is not False:
            raise ValueError('Adjacent-mail saved proof differs')
    return {'case_id':CASE,'candidates':list(CANDIDATES),
            'offline_negative_and_terminal_saved_checked':True,
            'fallback_changes_isolated':True,
            'actual_mail_absence_established':False,
            'physical_acceptance_claimed':False}


def digest_from_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == '__main__':
    print(json.dumps(check(),indent=2))
