import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    suffix = entry['case_id'].removeprefix(HERE.name + '__')
    primary = json.loads((HERE / entry['construction']).read_text())
    fallback = json.loads(json.dumps(primary))
    for file in fallback['files']:
        if file['path'] == 'runner.py':
            text = file['content']
            assert 'thickness=.08' in text and 'thickness=.09' in text
            text = text.replace('thickness=.08', 'thickness=.16').replace('thickness=.09', 'thickness=.16')
            if suffix != 'assisted':
                text = text.replace('life_time=31', 'life_time=.15')
                needle = '                native_frame = world.tick()'
                assert needle in text
                moving_marker = '''                if helper is None:
                    marker_position = walker.get_transform().location
                    world.debug.draw_line(
                        carla.Location(x=marker_position.x, y=marker_position.y,
                                       z=marker_position.z + .8),
                        carla.Location(x=marker_position.x + .35,
                                       y=marker_position.y, z=marker_position.z),
                        thickness=.16, color=carla.Color(255, 255, 255),
                        life_time=.15)
                    if marker == 'white_red_tipped_cane':
                        world.debug.draw_line(
                            carla.Location(x=marker_position.x + .28,
                                           y=marker_position.y,
                                           z=marker_position.z + .15),
                            carla.Location(x=marker_position.x + .35,
                                           y=marker_position.y,
                                           z=marker_position.z),
                            thickness=.16, color=carla.Color(255, 0, 0),
                            life_time=.15)
'''
                text = text.replace(needle, moving_marker + needle)
            if suffix == 'assisted':
                text = text.replace('carla.Location(x=-1.2, y=-4.6, z=28.1)',
                                    'carla.Location(x=-.55, y=-4.6, z=28.1)')
                needle = '''                    walker.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(0, 1, 0), speed=.5))'''
                assert needle in text
                text = text.replace(needle, needle + '''
                    if helper is not None:
                        helper.apply_control(carla.WalkerControl(
                            direction=carla.Vector3D(0, 1, 0), speed=.5))''')
            file['content'] = text
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['candidate_id'] = 'fallback1'
            file['content'] = json.dumps(config, indent=2) + '\n'
    fallback['status'] = 'partial_native_fallback_draft_physical_unverified'
    path = HERE / 'draft-exact' / suffix / 'fallback1' / 'construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fallback, indent=2) + '\n')
    entry['candidates'] = [{
        'id': 'fallback1',
        'construction': str(path.relative_to(HERE)),
        'construction_sha256': sha(path),
        'trigger': ({
            'source': 'original Native assistant/person pose rows and four-camera frames',
            'metric': 'assistant-person separation throughout crossing interval',
            'failure_condition': 'primary assistant does not remain visibly adjacent to the crossing person',
        } if suffix == 'assisted' else {
            'source': 'original Native four-camera frames and blind-person context',
            'metric': 'cane marker stroke visibility and walker attachment in crossing interval',
            'failure_condition': 'primary white or red-tipped cane marker is not visibly attached to the crossing person',
        }),
        'changed_knobs': ([
            'assistant starting offset: 1.2 to 0.55 m',
            'assistant control: stationary to synchronized walking request',
        ] if suffix == 'assisted' else [
            'authored cane debug stroke thickness: 0.08/0.09 to 0.16',
            'authored cane marker position: fixed initial pose to per-tick walker pose',
        ]),
    }]
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('fallbacks', len(manifest['cases']), sha(manifest_path))
