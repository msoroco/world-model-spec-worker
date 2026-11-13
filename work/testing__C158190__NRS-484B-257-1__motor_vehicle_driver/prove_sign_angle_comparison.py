"""Independent CPU audit of the unselected three-angle sign-face comparison."""

import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LABELS = ('minus_015', 'zero', 'plus_015')
ANGLES = (-0.15, 0.0, 0.15)
PREFIX = ROOT.name + '__yield_nearest_view_sign_angle_'
COMPARISON = 'same_approach_sign_face_angle_minus_015_zero_plus_015'
VARIABLE_SOURCES = {'road.xodr', 'control_inventory.jsonl', 'capture/manifest.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_returned_proofs(entries, result_tests, *, read_bytes=None):
    """Check the files shipped with this return, including negative evidence."""
    read_bytes = read_bytes or (lambda path: path.read_bytes())
    bound = {item['log']: item for item in result_tests}
    checked = []

    def payload(relative):
        path = ROOT / relative
        raw = read_bytes(path)
        require(raw is not None, 'Returned proof missing: ' + relative)
        return raw, hashlib.sha256(raw).hexdigest()

    for entry in entries:
        case_id = entry['case_id']
        label = case_id.split('sign_angle_')[1]
        folder = f'cases/sign_angle_{label}'
        for name, expected_format in (('compatibility.log', 'worker-package-compatibility'),
                                      ('saved.log', 'worker-saved-processing')):
            relative = f'{folder}/{name}'
            raw, digest = payload(relative)
            require(relative in bound and bound[relative]['exit_code'] == 0
                    and bound[relative]['sha256'] == digest,
                    'Returned primary result binding differs: ' + relative)
            receipt = json.loads(raw)
            require(receipt['format'] == expected_format and receipt['case_id'] == case_id
                    and receipt['passed'] is True,
                    'Returned primary receipt differs: ' + relative)
            if name == 'compatibility.log':
                require(receipt['candidate_id'] == 'primary'
                        and receipt['construction_sha256'] == entry['construction_sha256']
                        and receipt['fixture_recipe_sha256'] == sha(REPO / entry['fixture_recipe'])
                        and receipt['negative_removed'] == 'visibility_rays.jsonl'
                        and {'selected_measurements', 'negative_case_source',
                             'lean_decoder', 'final_decode'} <= set(receipt['checks']),
                        'Returned primary compatibility lacks exact proofs')
            else:
                require(receipt['recorded_only'] is True
                        and receipt['originals_preserved'] is True
                        and receipt['physical_acceptance_claimed'] is False
                        and receipt['legal_acceptance_claimed'] is False,
                        'Returned primary saved processing differs')
        require(len(entry['candidates']) == 3, 'Three returned fallbacks required')
        for candidate in entry['candidates']:
            ident = candidate['id']
            require(ident in ('fallback1', 'fallback2', 'fallback3'),
                    'Unexpected fallback identity')
            require(sha(ROOT / candidate['construction']) == candidate['construction_sha256'],
                    'Returned fallback construction differs')
            offline = candidate['offline']
            raw, digest = payload(offline['log'])
            require(offline['exit_code'] == 0 and offline['log_sha256'] == digest
                    and offline['construction_sha256'] == candidate['construction_sha256']
                    and json.loads(raw)['offline_passed'] is True,
                    'Returned fallback offline proof differs')
            compat = candidate['compatibility']
            raw, digest = payload(compat['receipt'])
            receipt = json.loads(raw)
            require(digest == compat['sha256'] and receipt['passed'] is True
                    and receipt['case_id'] == case_id and receipt['candidate_id'] == ident
                    and receipt['construction_sha256'] == candidate['construction_sha256']
                    and receipt['fixture_recipe_sha256'] == sha(REPO / candidate['fixture_recipe'])
                    and receipt['negative_removed'] == 'visibility_rays.jsonl',
                    'Returned fallback compatibility differs')
            positive_raw, positive_digest = payload(compat['log'])
            negative_raw, negative_digest = payload(compat['negative_log'])
            require(b'Missing required source: visibility_rays.jsonl' in negative_raw
                    and positive_digest == receipt['log_sha256']
                    and negative_digest == receipt['negative_log_sha256'],
                    'Returned fallback positive/negative logs differ')
            saved_suffix = '-source-saved-v1' if ident == 'fallback1' else '-saved-v1'
            saved_path = REPO / (f'.runtime-work/c158190-sign-angle-{label}-{ident}'
                                 + saved_suffix + '/v0001/processing.json')
            saved = read(saved_path)
            require(sha(saved_path) == candidate['saved_processing_sha256']
                    and saved['case_id'] == case_id and saved['candidate_id'] == ident
                    and saved['passed'] is True and saved['recorded_only'] is True
                    and saved['originals_preserved'] is True
                    and saved['physical_acceptance_claimed'] is False
                    and saved['legal_acceptance_claimed'] is False,
                    'Fallback saved processing binding differs')
            checked.append({'case_id': case_id, 'candidate_id': ident,
                            'returned_compatibility_sha256': digest,
                            'returned_negative_log_sha256': negative_digest})
    return checked


def audit(entries, constructions, recipes, roads, controls, captures, *, verify_sources=True):
    require(all(len(items) == 3 for items in
                (entries, constructions, recipes, roads, controls, captures)),
            'Sign comparison requires three exact cases')
    common_config = None
    common_files = None
    common_sources = None
    common_road = None
    common_controls = None
    common_capture = None
    for label, angle, entry, construction, recipe, road_text, history, capture in zip(
            LABELS, ANGLES, entries, constructions, recipes, roads, controls, captures):
        case_id = PREFIX + label
        require(entry['case_id'] == case_id and construction['case_id'] == case_id,
                'Sign comparison case identity differs')
        files = {item['path']: item['content'] for item in construction['files']}
        require(len(files) == len(construction['files'])
                and road_text == files['native-map-plan/yield-nearest-view.xodr'],
                'Authored road differs from exact construction')
        operational = {name: content.replace('yield_nearest_view_sign_angle_' + label,
                                             'yield_nearest_view_sign_angle_TARGET')
                       for name, content in files.items()
                       if name not in ('config.json', 'native-map-plan/yield-nearest-view.xodr')
                       and not name.startswith('tests/')}
        if common_files is None:
            common_files = operational
        require(operational == common_files, 'Fixed runner, controller or camera code changed')
        config = json.loads(files['config.json'])
        require(config['selected_case_id'] == case_id
                and config['rate_hz'] == 20 and config['duration_s'] == 30,
                'Fixed capture profile or case changed')
        config['selected_case_id'] = PREFIX + 'TARGET'
        config['supported_case_ids'] = [PREFIX + 'TARGET' if item == case_id else item
                                        for item in config['supported_case_ids']]
        if common_config is None:
            common_config = config
        require(config == common_config, 'Fixed config, actors or cameras changed')
        sources = {item['path']: item for item in recipe['sources']}
        require(len(sources) == len(recipe['sources']) and set(sources) >= VARIABLE_SOURCES,
                'Original source inventory incomplete')
        if verify_sources:
            for item in sources.values():
                require(sha(REPO / item['source']) == item['sha256'],
                        'Original source hash changed: ' + item['path'])
        fixed = {name: item['sha256'] for name, item in sources.items()
                 if name not in VARIABLE_SOURCES}
        if common_sources is None:
            common_sources = fixed
        require(fixed == common_sources
                and recipe['generator']['sha256'] == recipes[0]['generator']['sha256']
                and (not verify_sources or
                     sha(REPO / recipe['generator']['source']) == recipe['generator']['sha256']),
                'Fixed original source or generator changed')
        road = ET.fromstring(road_text)
        sign = road.find("./road[@id='158190']/signals/signal")
        require(sign is not None and sign.attrib['id'] == '1581901'
                and sign.attrib['t'] == '-3.8'
                and abs(float(sign.attrib['hOffset']) - angle) < 1e-12,
                'Authored sign angle or fixed lane offset changed')
        require(sign.find('validity').attrib == {'fromLane': '-1', 'toLane': '-1'},
                'Governed lane changed')
        sign.attrib['hOffset'] = 'TARGET'
        normalized_road = ET.tostring(road)
        if common_road is None:
            common_road = normalized_road
        require(normalized_road == common_road,
                'Road geometry changed beyond sign hOffset')
        require(len(history) == 600, 'Original sign control history lacks 600 frames')
        normalized_controls = copy.deepcopy(history)
        for index, row in enumerate(normalized_controls):
            sign_pose = row['yield_sign']['native_rotation_deg']
            require(row['frame'] == 100 + index and row['yield_sign']['actor_id'] == 12
                    and row['yield_sign']['blueprint'] == 'traffic.yield'
                    and abs(sign_pose['yaw'] - angle * 180 / math.pi) < 1e-9
                    and sign_pose['pitch'] == sign_pose['roll'] == 0.0,
                    'Original diagnostic sign pose or frame changed')
            sign_pose['yaw'] = 'TARGET'
        if common_controls is None:
            common_controls = normalized_controls
        require(normalized_controls == common_controls,
                'Fixed original sign-control rows changed')
        require(capture['sources']['road.xodr'] == sources['road.xodr']['sha256'],
                'Capture manifest road hash differs')
        normalized_capture = copy.deepcopy(capture)
        normalized_capture['case_id'] = PREFIX + 'TARGET'
        normalized_capture['sources']['road.xodr'] = 'TARGET'
        if common_capture is None:
            common_capture = normalized_capture
        require(normalized_capture == common_capture,
                'Capture manifest changed beyond case and road hash')
    return common_sources


def main():
    plan = read(ROOT / 'case-plan.json')
    comparison = next(item for item in plan['comparisons']
                      if item['comparison_id'] == COMPARISON)
    require(comparison['case_ids'] == [PREFIX + label for label in LABELS],
            'Planned sign-angle comparison differs')
    manifest = read(ROOT / 'sign-angle-compatibility-manifest.json')
    entries = manifest['cases']
    constructions = [read(ROOT / entry['construction']) for entry in entries]
    recipes = [read(REPO / entry['fixture_recipe']) for entry in entries]
    sources = [{item['path']: item for item in recipe['sources']} for recipe in recipes]
    roads = [(REPO / source['road.xodr']['source']).read_text() for source in sources]
    controls = [rows(REPO / source['control_inventory.jsonl']['source']) for source in sources]
    captures = [read(REPO / source['capture/manifest.json']['source']) for source in sources]
    fixed_sources = audit(entries, constructions, recipes, roads, controls, captures)
    returned = audit_returned_proofs(entries, read(ROOT / 'result.json')['tests'])
    missing_path = ROOT / entries[0]['candidates'][0]['compatibility']['negative_log']
    def missing_reader(path):
        return None if path == missing_path else path.read_bytes()
    try:
        audit_returned_proofs(entries, read(ROOT / 'result.json')['tests'],
                              read_bytes=missing_reader)
    except ValueError as exc:
        require('Returned proof missing' in str(exc), 'Missing proof rejected for wrong reason')
    else:
        raise ValueError('Missing returned negative proof accepted')
    changed_path = ROOT / entries[1]['candidates'][1]['compatibility']['receipt']
    def changed_reader(path):
        return path.read_bytes() + b' ' if path == changed_path else path.read_bytes()
    try:
        audit_returned_proofs(entries, read(ROOT / 'result.json')['tests'],
                              read_bytes=changed_reader)
    except ValueError as exc:
        require('Returned fallback compatibility differs' in str(exc),
                'Changed proof rejected for wrong reason')
    else:
        raise ValueError('Changed returned receipt accepted')
    negative = []
    tampered = list(roads)
    require(tampered[1].count('hOffset="0.00"') == 1,
            'Expected unique zero-angle source')
    tampered[1] = tampered[1].replace('hOffset="0.00"', 'hOffset="0.03"', 1)
    try:
        audit(entries, constructions, recipes, tampered, controls, captures, verify_sources=False)
    except ValueError:
        negative.append('changed_sign_angle_rejected')
    tampered = copy.deepcopy(controls)
    tampered[2][20]['yield_sign']['native_rotation_deg']['yaw'] += 1.0
    try:
        audit(entries, constructions, recipes, roads, tampered, captures, verify_sources=False)
    except ValueError:
        negative.append('changed_original_pose_rejected')
    tampered = copy.deepcopy(recipes)
    next(item for item in tampered[1]['sources'] if item['path'] == 'visibility_rays.jsonl')['sha256'] = '0' * 64
    try:
        audit(entries, constructions, tampered, roads, controls, captures, verify_sources=False)
    except ValueError:
        negative.append('changed_fixed_source_rejected')
    require(len(negative) == 3, 'Comparison negative tests did not reject changes')
    receipts = []
    for label, entry, recipe, source in zip(LABELS, entries, recipes, sources):
        compat = REPO / f'.runtime-work/c158190-sign-angle-{label}-compat-v1/compatibility.json'
        saved = REPO / f'.runtime-work/c158190-sign-angle-{label}-saved-v1/v0001/processing.json'
        c, s = read(compat), read(saved)
        require(c['passed'] is True and c['case_id'] == entry['case_id']
                and c['construction_sha256'] == entry['construction_sha256']
                and c['fixture_recipe_sha256'] == sha(REPO / entry['fixture_recipe'])
                and s['passed'] is True and s['recorded_only'] is True
                and s['originals_preserved'] is True
                and s['physical_acceptance_claimed'] is False
                and s['legal_acceptance_claimed'] is False,
                'Exact sign-angle compatibility or saved receipt differs')
        receipts.append({'case_id': entry['case_id'],
                         'road_sha256': source['road.xodr']['sha256'],
                         'control_inventory_sha256': source['control_inventory.jsonl']['sha256'],
                         'compatibility_sha256': sha(compat),
                         'saved_processing_sha256': sha(saved)})
    print(json.dumps({'format': 'c158190-sign-angle-independent-comparison-audit',
                      'comparison_id': COMPARISON, 'authored_angles_rad': ANGLES,
                      'fixed_source_sha256': fixed_sources, 'negative_checks': negative,
                      'returned_fallbacks': returned,
                      'returned_negative_checks': ['missing_negative_log_rejected',
                                                   'changed_compatibility_receipt_rejected'],
                      'receipts': receipts, 'cpu_comparison_passed': True,
                      'native_sign_pose_proven': False,
                      'original_pixel_face_proven': False,
                      'legal_conclusion': 'unresolved'}, indent=2))


if __name__ == '__main__':
    main()
