"""Audit structural other-vehicle cell binding in the red-control draft."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
from unittest.mock import patch

import native_runner
from source_measurement import analyze_control, load_rows


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = HERE/'fixtures/law_required_stop-sources'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_inventory(rows, light_id):
    if len(rows) != 600:
        raise ValueError('Incomplete 30-second control-cell source history')
    follower = None
    associated = 0
    for row in rows:
        inventory = row.get('scene_actor_inventory', {})
        actors = inventory.get('actors', [])
        followers = [a for a in actors if a.get('type_id') == 'vehicle.synthetic_follower']
        lights = [a for a in actors if a.get('actor_id') == light_id and
                  a.get('type_id') == 'traffic.traffic_light']
        if len(followers) != 1 or len(lights) != 1:
            raise ValueError('Other-vehicle focal actor or additional light absent')
        if followers[0]['actor_id'] == light_id:
            raise ValueError('Follower and supplemental light identities collide')
        if follower is None:
            follower = followers[0]['actor_id']
        elif follower != followers[0]['actor_id']:
            raise ValueError('Following vehicle identity changed')
        control = row.get('governing_control_state', {})
        if control.get('control_actor_id') != light_id:
            raise ValueError('Governing control source identity changed')
        if control.get('ego_associated_control_id') == light_id:
            associated += 1
        if not row['following_on_driving_lane']:
            raise ValueError('Focal other vehicle left the driving lane')
    if not associated:
        raise ValueError('No source-visible ego/control association')
    return follower, associated


def inspect_runner(light_id):
    spec = importlib.util.spec_from_file_location(
        'c179480_native_runner_fakes', HERE/'tests/test_native_runner.py')
    fake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fake)
    world = fake.FakeWorld()
    light = types.SimpleNamespace(id=light_id, type_id='traffic.traffic_light')
    world.get_actors = lambda: types.SimpleNamespace(find=lambda ident: light if ident == light_id else None)
    fixture = fake.NativeRunnerTest()
    fixture.setUp()
    survey = dict(fixture.survey, governing_traffic_light_id=light_id)
    class ReachedCapture(Exception):
        pass
    seen = []
    def capture(_world, _carla, ego, follower, _library, _stop, _attempt, **options):
        if len(world.actors) != 2 or ego is not world.actors[0] or follower is not world.actors[1]:
            raise ValueError('Native other-vehicle pair missing')
        if options.get('governing_light') is not light:
            raise ValueError('Supplemental light not passed to source capture')
        seen.append('follower_and_light_supplied')
        raise ReachedCapture
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work', prefix='c179480-cell-') as tmp:
        with patch.object(native_runner, 'acquire_with_world_restore', side_effect=capture):
            try:
                native_runner.run(types.SimpleNamespace(get_world=lambda: world),
                                  fixture.carla, survey, Path(tmp)/'attempt',
                                  'law_required_stop')
            except ReachedCapture:
                pass
    if seen != ['follower_and_light_supplied'] or not all(a.destroyed for a in world.actors):
        raise ValueError('Native cell actor or cleanup proof incomplete')
    return seen[0]


def audit():
    frozen = REPO/'inputs'/HERE.name/'assignment.json'
    assignment = json.loads(frozen.read_text())
    if (assignment['cell_id'] != 'C179480' or assignment['cell']['control'] != 'other_vehicle'
            or assignment['law_id'] != 'NRS-484B-627-2'):
        raise ValueError('Frozen cell/law binding changed')
    map_path = SOURCE/'native-map-readback.json'
    readback = json.loads(map_path.read_text())
    light_id = readback['surveyed_governing_traffic_light_id']
    actor = SOURCE/'native-actors.jsonl'
    frame_map = SOURCE/'video_frames.jsonl'
    rows = load_rows(actor, frame_map)
    follower, associated = inspect_inventory(rows, light_id)
    control = analyze_control(actor, frame_map, expected_control_id=light_id,
                              source_kind='synthetic_native_sample')
    if not control['associated_red_frames']:
        raise ValueError('No source-visible red association')
    runner = inspect_runner(light_id)
    missing_follower = [dict(row) for row in rows]
    missing_follower[0]['scene_actor_inventory'] = dict(
        missing_follower[0]['scene_actor_inventory'], actors=[a for a in
        missing_follower[0]['scene_actor_inventory']['actors']
        if a['actor_id'] != follower])
    wrong_light = [dict(row) for row in rows]
    wrong_light[0]['governing_control_state'] = dict(
        wrong_light[0]['governing_control_state'], control_actor_id=light_id+1)
    negatives = []
    for label, changed in [('missing_follower',missing_follower),('wrong_light',wrong_light)]:
        try:
            inspect_inventory(changed,light_id)
        except ValueError:
            negatives.append(label)
        else:
            raise ValueError('Cell-binding negative accepted: '+label)
    return {
        'format':'c179480-other-vehicle-plus-light-cell-audit-v1',
        'frozen_assignment_sha256':sha(frozen),
        'actor_source_sha256':sha(actor),
        'frame_map_sha256':sha(frame_map),
        'map_readback_sha256':sha(map_path),
        'focal_cell_control':'other_vehicle',
        'follower_actor_id':follower,
        'supplemental_light_actor_id':light_id,
        'associated_control_frames':associated,
        'associated_red_frames':len(control['associated_red_frames']),
        'runner_check':runner,
        'negative_rejections':negatives,
        'scope':'synthetic source and Native call-path structural binding only',
        'governing_law_applicability_verified':False,
        'original_native_or_legal_acceptance_claimed':False,
    }


if __name__ == '__main__':
    path = HERE/'update161-control-cell-audit.json'
    result=audit()
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'follower':result['follower_actor_id'],
                      'light':result['supplemental_light_actor_id'],
                      'red_frames':result['associated_red_frames'],
                      'negatives':result['negative_rejections']}))
