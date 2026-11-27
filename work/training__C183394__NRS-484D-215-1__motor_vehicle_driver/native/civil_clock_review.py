"""Independent original UTC-tick to dated Nevada sun-event review guard."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, item):
    relative = item.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Civil review source must stay inside original attempt')
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file() or sha(path) != item.get('sha256'):
        raise ValueError('Civil review original source hash changed')
    return path


def aware(value):
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Civil event must include timezone')
    return instant


def verify(review, root, case_id):
    if review.get('format') != 'c183394-civil-clock-review' or \
            review.get('source_kind') != 'independent_original_review' or \
            review.get('case_id') != case_id or not review.get('reviewer_id') or \
            review.get('synthetic_diagnostic') is True:
        raise ValueError('Independent original civil-time review missing')
    items = review.get('sources', {})
    if set(items) != {'beam_rows', 'frame_map', 'lighting_trigger', 'sun_events',
                      'acquisition_provenance'}:
        raise ValueError('Civil review source inventory incomplete')
    paths = {name: source(root, item) for name, item in items.items()}
    rows = [json.loads(line) for line in paths['beam_rows'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['frame_map'].read_text().splitlines()]
    trigger = json.loads(paths['lighting_trigger'].read_text())
    sun = json.loads(paths['sun_events'].read_text())
    provenance = json.loads(paths['acquisition_provenance'].read_text())
    if provenance.get('provenance_kind') != 'native' or \
            provenance.get('diagnostic_fixture') is not False:
        raise ValueError('Civil interval needs original Native provenance')
    if len(rows) != 600 or len(frames) != 600 or trigger.get('lighting_trigger') != 'night_interval' or \
            not trigger.get('utc_clock_capture') or not trigger.get('local_site_and_sun_event_review_required'):
        raise ValueError('Original night-request clock source incomplete')
    if not sun.get('source') or not sun.get('site') or not sun.get('timezone') or \
            sun.get('site') != review.get('Nevada_site') or \
            sun.get('source') != review.get('sun_event_source'):
        raise ValueError('Dated Nevada sun-event provenance missing')
    try:
        zone = ZoneInfo(sun['timezone'])
    except (KeyError, ValueError) as error:
        raise ValueError('Civil event timezone invalid') from error
    sunset, sunrise = aware(sun['sunset_iso']), aware(sun['sunrise_iso'])
    if sunset.astimezone(zone).utcoffset() != sunset.utcoffset() or \
            sunrise.astimezone(zone).utcoffset() != sunrise.utcoffset() or \
            not sunset < sunrise:
        raise ValueError('Sun-event timezone or order differs')
    clocks = []
    for i, (row, frame) in enumerate(zip(rows, frames)):
        if row.get('frame') != i or frame.get('video_frame') != i or \
                row.get('native_frame') != frame.get('native_frame') or \
                row.get('time_s') != frame.get('time_s'):
            raise ValueError('Civil clock original frame join differs')
        clock = aware(row['civil_time_utc'])
        if clock.utcoffset() != timezone.utc.utcoffset(clock):
            raise ValueError('Original tick clock must be UTC')
        clocks.append(clock)
    if any(b <= a for a, b in zip(clocks, clocks[1:])) or \
            clocks[0] < sunset + timedelta(minutes=30) or \
            clocks[-1] > sunrise - timedelta(minutes=30):
        raise ValueError('Original frames outside exact sunset/sunrise interval')
    if review.get('first_frame_utc') != clocks[0].isoformat() or \
            review.get('last_frame_utc') != clocks[-1].isoformat():
        raise ValueError('Civil review frame clock differs')
    return {'case_id': case_id, 'joined_frames': 600,
            'civil_interval_source_reviewed': True, 'legal_verdict_claimed': False}
