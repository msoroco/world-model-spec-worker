"""Build exact mail-adjacent/deposit CPU drafts from tested short-stop scaffolds."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback

CASE = 'mail_adjacent_deposit'


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source transform anchor differs: ' + before[:60])
    return source.replace(before, after)


def runner(source):
    source = once(source, 'import business_activity', 'import mail_activity')
    source = once(source, "authored['sign_readback']['present'] or authored['mailbox_readback']['present']:",
                  "authored['sign_readback']['present'] or not authored['mailbox_readback']['present']:")
    source = once(source, "cfg.get('native_blueprint') != 'vehicle.carlamotors.firetruck' or \\\n       cfg.get('service_class') != 'emergency_vehicle' or \\\n       cfg.get('activity_request') != 'business_activity':",
                  "cfg.get('native_blueprint') != 'vehicle.tesla.model3' or \\\n       cfg.get('service_class') != 'ordinary' or \\\n       cfg.get('activity_request') != 'mail_deposit':")
    source = once(source, "        (output / 'native-map-readback.json').write_text", """        native_boxes = native_root.findall(
            './/road[@id="150142"]/objects/object[@id="15014202"]')
        if len(native_boxes) != 1 or abs(float(native_boxes[0].get('s'))-40) > .01 or \\
           abs(float(native_boxes[0].get('t'))+7.4) > .01:
            raise RuntimeError('Native mail-drop object readback differs')
        (output / 'native-map-readback.json').write_text""")
    source = once(source, "        walker = business_activity.spawn(world, library, carla)\n        owned.append(walker)",
                  "        walker, parcel = mail_activity.spawn(world, library, carla)\n        owned.extend((walker, parcel))")
    source = once(source, "(output/'native-service-worker-actors.jsonl').open('x') as worker_rows, \\",
                  "(output/'native-mail-worker-actors.jsonl').open('x') as worker_rows, \\\n             (output/'native-mail-parcel-inventory.jsonl').open('x') as parcel_rows, \\")
    source = once(source, "                business_activity.control(walker, carla, i,",
                  "                mail_activity.control(walker, parcel, carla, i,")
    source = once(source, "                    **native_walker_pose(walker)}, allow_nan=False)+'\\n')",
                  "                    **native_walker_pose(walker)}, allow_nan=False)+'\\n')\n"
                  "                parcel_alive = parcel.is_alive\n"
                  "                parcel_xy = parcel.get_transform().location if parcel_alive else None\n"
                  "                parcel_rows.write(json.dumps({\n"
                  "                    'frame': i, 'native_frame': frame, 'time_s': time_s,\n"
                  "                    'source_kind': 'original_native', 'present': parcel_alive,\n"
                  "                    'actor_id': parcel.id if parcel_alive else None,\n"
                  "                    'blueprint': parcel.type_id if parcel_alive else None,\n"
                  "                    'center_native_xy_m': [parcel_xy.x, parcel_xy.y] if parcel_alive else None},\n"
                  "                    allow_nan=False)+'\\n')")
    source = once(source, "('native-raw-actors.jsonl','native-service-worker-actors.jsonl',",
                  "('native-raw-actors.jsonl','native-mail-worker-actors.jsonl',\n            'native-mail-parcel-inventory.jsonl',")
    source = once(source, "                actor.destroy()\n            except BaseException as exc:",
                  "                if actor.is_alive:\n                    actor.destroy()\n            except BaseException as exc:")
    return source


def finalizer(source):
    source = once(source, 'from business_activity import derive as derive_business_activity',
                  'from mail_activity import derive as derive_mail_activity')
    source = source.replace('native-service-worker-actors.jsonl', 'native-mail-worker-actors.jsonl')
    source = once(source, "'native-mail-worker-actors.jsonl',\n                 'video_frames.jsonl'",
                  "'native-mail-worker-actors.jsonl','native-mail-parcel-inventory.jsonl',\n                 'video_frames.jsonl'")
    source = once(source, "    walker_rows=rows(attempt,'native-mail-worker-actors.jsonl')",
                  "    walker_rows=rows(attempt,'native-mail-worker-actors.jsonl')\n"
                  "    parcel_rows=rows(attempt,'native-mail-parcel-inventory.jsonl')")
    source = once(source, "    activity=derive_business_activity(walker_rows,actor_rows,\n                                      schedule['stationary_first_frame'])",
                  "    activity=derive_mail_activity(walker_rows,parcel_rows,actor_rows,\n                                  schedule['stationary_first_frame'])")
    source = once(source, "    if sign != authored['sign_readback'] or sign.get('present'):",
                  "    if sign != authored['sign_readback'] or sign.get('present') or \\\n            map_readback.get('mailbox_readback') != authored['mailbox_readback'] or \\\n            not authored['mailbox_readback']['present']:")
    source = source.replace("'native-mail-worker-actors.jsonl')}",
                            "'native-mail-worker-actors.jsonl','native-mail-parcel-inventory.jsonl')}")
    return source


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    exact = ROOT.name + '__' + CASE
    case = next(row for row in matrix['cases'] if row['case_id'] == exact)
    if (case['service_class'], case['sign_classes'], case['activity_request'],
            case['mailbox_requested'], case['requested_stationary_duration_s']) != (
            'ordinary', [], 'mail_deposit', True, 12):
        raise ValueError('Frozen adjacent-mail scope changed')
    road = construct(case)
    if not readback(road)['mailbox_readback']['present']:
        raise ValueError('Authored mailbox missing')
    output = []
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        prefix = ROOT / ('selected-primary' if candidate == 'primary' else 'selected-fallbacks')
        prior = prefix / 'emergency_vehicle_unsigned_business'
        target = prefix / CASE
        if candidate != 'primary':
            prior /= candidate
            target /= candidate
        package = json.loads((prior / 'construction.json').read_text())
        files = {row['path']: row['content'] for row in package['files']}
        config = json.loads(files['config.json'])
        config.update(case_id=exact, selected_case_id=exact,
                      supported_case_ids=[exact], service_class='ordinary',
                      native_blueprint='vehicle.tesla.model3',
                      activity_request='mail_deposit', road_sha256=digest(road),
                      service_identity_source='requested_ordinary_blueprint_native_readback_pending')
        config['risk_trigger'] = config['risk_trigger'].replace(
            'firetruck body', 'ordinary vehicle body').replace(
            'service-worker', 'mail worker')
        files['config.json'] = encoded(config)
        files['red-curb-road.xodr'] = road
        files['runner.py'] = runner(files['runner.py'])
        files['finalize_selected.py'] = finalizer(files['finalize_selected.py'])
        files['mail_activity.py'] = (ROOT / 'native/mail_activity.py').read_text()
        files.pop('business_activity.py')
        files['tests/test_selected.py'] = files['tests/test_selected.py'].replace(
            'vehicle.carlamotors.firetruck', 'vehicle.tesla.model3')
        package['case_id'] = exact
        package['files'] = [{'path': path, 'content': content} for path, content in files.items()]
        package['recording_description']['limitations'][-1] = (
            'Authored OpenDRIVE mail-drop object, ordinary vehicle, worker and parcel '
            'disappearance need original Native/pixel review. Actual U.S. mail deposit '
            'and statutory expeditiousness remain unverified.')
        package['measurement_plan'] = {'source': 'retained ordinary body, velocity, '
            'mail-drop map readback, worker and parcel inventory, four cameras',
            'finalizer': 'finalize_selected.py', 'legal_verdict': None}
        target.mkdir(parents=True, exist_ok=True)
        path = target / 'construction.json'
        path.write_text(encoded(package))
        output.append({'case_id': exact, 'candidate': candidate,
                       'construction': str(path.relative_to(ROOT)),
                       'sha256': digest(path.read_text()),
                       'actual_mail_deposit_established': False})
    return output


if __name__ == '__main__':
    print(encoded(build()), end='')
