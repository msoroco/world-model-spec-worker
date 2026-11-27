"""Source-bound review guard for the three incorporated NRS 484D.100 triggers.

This validates provenance and the exact trigger-specific observation contract.
It does not turn a CARLA weather label or synthetic fixture into legal evidence.
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

BRANCHES = ('civil_sun_interval', '1000ft_discernibility', 'official_device_direction')
REQUIRED = {
    'civil_sun_interval': {'frame_clock', 'sun_events'},
    '1000ft_discernibility': {'target_range', 'forward_video', 'frame_map'},
    'official_device_direction': {'device_authority', 'device_state', 'forward_video', 'frame_map'},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aware(value):
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Trigger civil clock requires timezone-aware source')
    return instant


def verify(review, root, case_id):
    root = Path(root).resolve()
    if review.get('format') != 'c183394-incorporated-trigger-review' or \
            review.get('source_kind') != 'independent_original_review' or \
            review.get('case_id') != case_id or not review.get('reviewer_id'):
        raise ValueError('Independent original lighting-trigger review missing')
    branch = review.get('branch')
    if branch not in BRANCHES:
        raise ValueError('Unknown incorporated lighting trigger')
    sources = review.get('sources')
    if not isinstance(sources, dict) or set(sources) != REQUIRED[branch]:
        raise ValueError('Trigger source inventory differs from exact branch')
    verified = {}
    for name, record in sources.items():
        relative = record.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Trigger source path must remain inside original attempt')
        path = (root/relative).resolve()
        if root not in path.parents or not path.is_file() or sha(path) != record.get('sha256'):
            raise ValueError('Original trigger source hash changed: '+name)
        verified[name] = path
    if branch == 'civil_sun_interval':
        clock = json.loads(verified['frame_clock'].read_text())
        sun = json.loads(verified['sun_events'].read_text())
        if clock.get('first_frame_iso') != review.get('first_frame_iso') or \
                clock.get('last_frame_iso') != review.get('last_frame_iso') or \
                clock.get('frames') != review.get('clock_joined_frames') or \
                sun.get('sunset_iso') != review.get('sunset_iso') or \
                sun.get('sunrise_iso') != review.get('sunrise_iso') or not sun.get('source'):
            raise ValueError('Civil clock or sun event review differs from source')
        sunset, sunrise = aware(review['sunset_iso']), aware(review['sunrise_iso'])
        first, last = aware(review['first_frame_iso']), aware(review['last_frame_iso'])
        if not sunset < sunrise or not first <= last or \
                first < sunset + timedelta(minutes=30) or \
                last > sunrise - timedelta(minutes=30):
            raise ValueError('Original frames outside exact sunset/sunrise interval')
        if review.get('clock_joined_frames') != 600:
            raise ValueError('Civil clock must join all 600 original frames')
    elif branch == '1000ft_discernibility':
        target = json.loads(verified['target_range'].read_text())
        if target.get('target_distance_ft') != review.get('target_distance_ft') or \
                target.get('target_kind') != review.get('target_kind'):
            raise ValueError('Original target range review differs from source')
        if review.get('target_distance_ft') != 1000 or \
                review.get('target_kind') not in ('person', 'vehicle') or \
                review.get('not_clearly_discernible') is not True or \
                not review.get('reviewed_frame_ids'):
            raise ValueError('Original 1000-foot target discernibility review missing')
    else:
        authority = json.loads(verified['device_authority'].read_text())
        state = json.loads(verified['device_state'].read_text())
        if authority.get('official_status_verified') != review.get('device_official_status_verified') or \
                state.get('direction_applies_to_ego') != review.get('device_direction_applies_to_ego'):
            raise ValueError('Original device review differs from source')
        if review.get('device_official_status_verified') is not True or \
                review.get('device_direction_applies_to_ego') is not True or \
                not review.get('reviewed_frame_ids'):
            raise ValueError('Original official-device direction review missing')
    if review.get('synthetic_diagnostic') is True:
        raise ValueError('Synthetic trigger cannot attest original activation')
    return {'case_id': case_id, 'branch': branch, 'sources_verified': sorted(sources),
            'original_trigger_reviewed': True, 'legal_verdict_claimed': False}
