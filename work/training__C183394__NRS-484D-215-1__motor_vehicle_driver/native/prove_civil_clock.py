"""Source-shaped CPU predicates for original UTC-tick civil-time review."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

from civil_clock_review import sha, verify


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
CASE = PACKAGE.name + '__selected_6fb122bc__condition_a'
SCRATCH = REPO / '.runtime-work' / 'c183394' / 'civil-clock-proof'
if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)
SOURCE = PACKAGE / 'fixture-source' / 'condition_a'
for name in ('beam-rows.jsonl', 'video_frames.jsonl', 'lighting-trigger-source.json'):
    shutil.copyfile(SOURCE / name, SCRATCH / name)
(SCRATCH / 'acquisition-provenance.json').write_text(json.dumps({
    'provenance_kind': 'native', 'diagnostic_fixture': False}) + '\n')
(SCRATCH / 'sun-events.json').write_text(json.dumps({
    'source': 'diagnostic source-shaped event contract; not a real sun-event attestation',
    'site': 'Las Vegas, Nevada', 'timezone': 'America/Los_Angeles',
    'sunset_iso': '2026-11-26T17:00:00-08:00',
    'sunrise_iso': '2026-11-27T06:30:00-08:00'}) + '\n')
names = {'beam_rows': 'beam-rows.jsonl', 'frame_map': 'video_frames.jsonl',
         'lighting_trigger': 'lighting-trigger-source.json',
         'sun_events': 'sun-events.json',
         'acquisition_provenance': 'acquisition-provenance.json'}
review = {'format': 'c183394-civil-clock-review',
          'source_kind': 'independent_original_review', 'case_id': CASE,
          'reviewer_id': 'CPU synthetic predicate', 'synthetic_diagnostic': False,
          'Nevada_site': 'Las Vegas, Nevada',
          'sun_event_source': 'diagnostic source-shaped event contract; not a real sun-event attestation',
          'first_frame_utc': '2026-11-27T09:00:00+00:00',
          'last_frame_utc': '2026-11-27T09:00:29.950000+00:00',
          'sources': {key: {'path': path, 'sha256': sha(SCRATCH / path)}
                      for key, path in names.items()}}
assert verify(review, SCRATCH, CASE)['joined_frames'] == 600
print('PASS source-shaped 600-frame civil-clock join; diagnostic only')


def rejects(changed, message):
    try:
        verify(changed, SCRATCH, CASE)
    except ValueError as error:
        print('PASS reject', message, str(error))
        return
    raise AssertionError('Civil guard accepted ' + message)


changed = deepcopy(review)
changed['synthetic_diagnostic'] = True
rejects(changed, 'declared synthetic review')
changed = deepcopy(review)
changed['first_frame_utc'] = '2026-11-27T08:00:00+00:00'
rejects(changed, 'stale clock claim')
changed = deepcopy(review)
changed['sources']['beam_rows']['sha256'] = '0' * 64
rejects(changed, 'changed original row source')
changed = deepcopy(review)
changed['Nevada_site'] = 'Reno, Nevada'
rejects(changed, 'changed Nevada site')
provenance = SCRATCH / 'acquisition-provenance.json'
provenance.write_text(json.dumps({'provenance_kind': 'synthetic_fixture',
                                  'diagnostic_fixture': True}) + '\n')
changed = deepcopy(review)
changed['sources']['acquisition_provenance']['sha256'] = sha(provenance)
rejects(changed, 'diagnostic acquisition provenance')
