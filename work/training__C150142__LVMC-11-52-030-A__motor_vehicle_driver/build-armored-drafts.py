"""Build the four text-6 armored alternatives with a visible body proxy.

The attached panels are a reproducible visual construction request.  Actual
armoring, service identity, sign pixels and legal necessity need later review.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback
from armored_proxy import BASE_BLUEPRINT, PANEL_BLUEPRINT

CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def adapt_runner(source):
    source = source.replace('import exception_duration\n',
                            'import exception_duration\nimport armored_proxy\n')
    source = source.replace('vehicle.carlamotors.firetruck', BASE_BLUEPRINT)
    source = source.replace("'emergency_vehicle'", "'armored_car'")
    source = source.replace("    schedule = exception_duration.plan({'case_id': cfg['case_id'],",
                            "    armored_proxy.validate(cfg)\n"
                            "    schedule = exception_duration.plan({'case_id': cfg['case_id'],", 1)
    needle = '        owned.append(ego)\n'
    if source.count(needle) != 1:
        raise ValueError('Vehicle spawn injection point changed')
    source = source.replace(needle, needle +
        "        panels, armor_readback = armored_proxy.spawn(world, library, carla, ego, cfg)\n"
        "        owned.extend(panels)\n"
        "        (output/'native-armor-proxy-readback.json').write_text(json.dumps({\n"
        "            'source_kind': 'native_readback', 'base_actor_id': ego.id,\n"
        "            'base_blueprint': ego.type_id, 'panels': armor_readback,\n"
        "            'legal_armored_identity_verified': False}, indent=2)+'\\n')\n")
    return source


def adapt_finalizer(source):
    source = source.replace('from exception_duration import plan as duration_plan\n',
                            'from exception_duration import plan as duration_plan\n'
                            'from armored_proxy import verify_readback\n')
    source = source.replace("'native-raw-actors.jsonl',", 
                            "'native-raw-actors.jsonl','native-armor-proxy-readback.json',", 1)
    marker = "    actor_rows=rows(attempt,'native-raw-actors.jsonl')\n"
    if source.count(marker) != 1:
        raise ValueError('Finalizer actor source injection point changed')
    source = source.replace(marker, marker +
        "    armor_proxy_readback=verify_readback(json.loads(source(attempt,\n"
        "        'native-armor-proxy-readback.json').read_text()), actor_rows, config)\n")
    source = source.replace("    hashes={name:sha(attempt/name) for name in\n",
                            "    hashes={name:sha(attempt/name) for name in\n")
    return source


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    records = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            new = 'armored_car_' + sign + '_' + activity
            old = 'emergency_vehicle_' + sign + '_' + activity
            exact = ROOT.name + '__' + new
            case = next(row for row in matrix['cases'] if row['case_id'] == exact)
            requested_activity = 'business_activity' if activity == 'business' else None
            expected_signs = ['armored_or_emergency'] if sign == 'signed' else []
            if (case['service_class'], case['sign_classes'],
                    case['activity_request'], case['mailbox_requested'],
                    case['requested_stationary_duration_s']) != (
                    'armored_car', expected_signs, requested_activity, False, 12):
                raise ValueError('Frozen armored case differs: ' + new)
            road = construct(case)
            if readback(road)['sign_readback']['displayed_classes'] != expected_signs:
                raise ValueError('Armored sign construction differs')
            for candidate in CANDIDATES:
                root = ROOT / ('selected-primary' if candidate == 'primary' else 'selected-fallbacks')
                source_path, target_path = root / old, root / new
                if candidate != 'primary':
                    source_path /= candidate
                    target_path /= candidate
                package = json.loads((source_path / 'construction.json').read_text())
                files = {row['path']: row['content'] for row in package['files']}
                config = json.loads(files['config.json'])
                if config['service_class'] != 'emergency_vehicle' or \
                   config['native_blueprint'] != 'vehicle.carlamotors.firetruck':
                    raise ValueError('Emergency source construction changed')
                config.update(case_id=exact, selected_case_id=exact,
                              supported_case_ids=[exact], service_class='armored_car',
                              native_blueprint=BASE_BLUEPRINT,
                              armor_proxy_kind='attached_box_panels_v1',
                              armor_panel_blueprint=PANEL_BLUEPRINT,
                              service_identity_source='requested_visual_proxy_not_legal_identity',
                              road_sha256=sha(road))
                if candidate != 'primary':
                    config['risk_trigger'] = config['risk_trigger'].replace(
                        'firetruck body', 'armored proxy body')
                files['config.json'] = encode(config)
                files['red-curb-road.xodr'] = road
                files['runner.py'] = adapt_runner(files['runner.py'])
                files['finalize_selected.py'] = adapt_finalizer(files['finalize_selected.py'])
                files['armored_proxy.py'] = (ROOT / 'native/armored_proxy.py').read_text()
                files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
                    'vehicle.carlamotors.firetruck', BASE_BLUEPRINT)
                package['case_id'] = exact
                package['files'] = [{'path': path, 'content': content}
                                    for path, content in files.items()]
                package['recording_description']['limitations'][-1] = (
                    'Sprinter body plus four attached box panels is an armored-looking '
                    'proxy only; armored-car legal identity, actual armor, pixel visibility '
                    'and necessary-business facts are unverified.')
                package['measurement_plan']['source'] = (
                    'retained Native Sprinter and attached-panel readback, worker inventory, '
                    'velocity, and signed or unsigned curb readback')
                target_path.mkdir(parents=True, exist_ok=True)
                target = target_path / 'construction.json'
                target.write_text(encode(package))
                records.append({'case_id': exact, 'candidate': candidate,
                                'construction': str(target.relative_to(ROOT)),
                                'sha256': sha(target.read_text()),
                                'visual_proxy_only': True})
    return records


if __name__ == '__main__':
    print(encode(build()), end='')
