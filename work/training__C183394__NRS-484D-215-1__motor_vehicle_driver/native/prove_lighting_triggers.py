"""CPU diagnostic tests of each incorporated trigger review guard."""
import json
import os
from pathlib import Path
import tempfile

from lighting_trigger_review import sha, verify


def put(root, name, value):
    path = root/name
    path.write_text(json.dumps(value)+'\n' if not isinstance(value, str) else value)
    return {'path': name, 'sha256': sha(path)}


case = 'diagnostic-exact-case'
with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
    root = Path(temp)
    common = {'format': 'c183394-incorporated-trigger-review',
              'source_kind': 'independent_original_review', 'case_id': case,
              'reviewer_id': 'cpu-predicate-fixture'}
    civil = dict(common, branch='civil_sun_interval',
        first_frame_iso='2026-11-27T18:00:00-08:00',
        last_frame_iso='2026-11-27T18:00:29.950000-08:00',
        sunset_iso='2026-11-27T17:00:00-08:00',
        sunrise_iso='2026-11-28T07:00:00-08:00', clock_joined_frames=600)
    civil['sources'] = {'frame_clock': put(root, 'clock.json', {'first_frame_iso': civil['first_frame_iso'],
        'last_frame_iso': civil['last_frame_iso'], 'frames': 600}),
        'sun_events': put(root, 'sun.json', {'sunset_iso': civil['sunset_iso'],
        'sunrise_iso': civil['sunrise_iso'], 'source': 'diagnostic fixture'})}
    assert verify(civil, root, case)['original_trigger_reviewed']
    wrong = dict(civil, first_frame_iso='2026-11-27T17:01:00-08:00')
    try:
        verify(wrong, root, case)
    except ValueError:
        pass
    else:
        raise AssertionError('Unsupported civil clock accepted')
    visibility = dict(common, branch='1000ft_discernibility', target_distance_ft=1000,
                      target_kind='vehicle', not_clearly_discernible=True,
                      reviewed_frame_ids=[0, 200, 599])
    visibility['sources'] = {'target_range': put(root, 'target.json',
        {'target_distance_ft': 1000, 'target_kind': 'vehicle'}),
        'forward_video': put(root, 'forward.bin', 'diagnostic video placeholder\n'),
        'frame_map': put(root, 'map.json', {'frames': 600})}
    assert verify(visibility, root, case)['original_trigger_reviewed']
    wrong = dict(visibility, target_distance_ft=999)
    try:
        verify(wrong, root, case)
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong 1000-foot target accepted')
    device = dict(common, branch='official_device_direction',
                  device_official_status_verified=True,
                  device_direction_applies_to_ego=True,
                  reviewed_frame_ids=[100, 101])
    device['sources'] = {'device_authority': put(root, 'authority.json',
        {'official_status_verified': True}), 'device_state': put(root, 'state.json',
        {'direction_applies_to_ego': True}), 'forward_video': visibility['sources']['forward_video'],
        'frame_map': visibility['sources']['frame_map']}
    assert verify(device, root, case)['original_trigger_reviewed']
    wrong = dict(device, synthetic_diagnostic=True)
    try:
        verify(wrong, root, case)
    except ValueError:
        pass
    else:
        raise AssertionError('Declared synthetic trigger accepted as original')
    wrong = dict(device, sources={**device['sources'], 'forward_video':
        {'path': 'forward.bin', 'sha256': '0'*64}})
    try:
        verify(wrong, root, case)
    except ValueError:
        pass
    else:
        raise AssertionError('Changed video source accepted')
print(json.dumps({'tested_branches': 3, 'negative_guards': 4,
                  'diagnostic_only': True, 'original_trigger_observed': False}))
