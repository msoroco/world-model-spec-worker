import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_native_scene import ref, site

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('saved_attempt', ROOT / 'saved_attempt.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)
audit_spec = importlib.util.spec_from_file_location('comparison_audit_saved', ROOT / 'comparison_audit.py')
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)


def packet(base, suffix):
    s = site(base)
    site_ref = ref(base, 'site.json', s)
    if suffix == 'green_clear':
        user = None
    elif suffix == 'green_vehicle_present':
        user = {'id': 'vehicle-2', 'kind': 'motor_vehicle', 'xy': [0, 0],
                'lawful_presence_source': 'reviewed-traffic-context.json'}
    else:
        user = {'id': 'pedestrian-2', 'kind': 'pedestrian',
                'xy': [0, 4] if suffix == 'green_pedestrian_late' else [0, 2.5],
                'lawful_presence_source': 'reviewed-pedestrian-context.json'}
    rows = []
    for frame, ego in enumerate(([-4, 0], [0, 0], [4, 0]), 1):
        other = [] if user is None else [dict(user)]
        if suffix == 'green_pedestrian_late' and frame > 1:
            other[0]['xy'] = [0, 2.5]
        rows.append({'frame': frame, 'official_head_id': 'head-7',
                     'facing_approach_id': 'north', 'lit_aspects': ['circular_green'],
                     'ego_xy': ego, 'other_users': other})
    event_ref = ref(base, 'events.json', rows)
    return {'assignment_id': saved.ASSIGNMENT, 'case_id': saved.ASSIGNMENT + '__' + suffix,
            'case_suffix': suffix, 'candidate': 'primary', 'attempt_id': 'attempt-1',
            'recording_id': 'diagnostic-only', 'site_ref': site_ref, 'event_ref': event_ref,
            'duration_frames': 3, 'camera_profile_sha256': 'camera-source-hash'}


class SavedAttemptTests(unittest.TestCase):
    def test_four_case_observations_and_comparisons(self):
        summaries = {}
        for suffix in saved.CASES:
            with tempfile.TemporaryDirectory() as d:
                p = packet(Path(d), suffix)
                summaries[suffix] = saved.process_saved(p, d)
                self.assertFalse(summaries[suffix]['physical_acceptance_claimed'])
                self.assertIsNone(summaries[suffix]['right_of_way_verdict'])
        for name, (left, right, _, _) in audit.PAIRS.items():
            self.assertTrue(audit.audit_pair(name, summaries[left], summaries[right])['exhibition_checked'])

    def test_rejects_changed_original_event_and_case(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = packet(base, 'green_clear')
            with self.assertRaisesRegex(saved.SourceError, 'wrong exact case ID'):
                saved.process_saved({**p, 'case_id': p['case_id'] + 'x'}, base)
            (base / 'events.json').write_text('[]')
            with self.assertRaisesRegex(saved.SourceError, 'source hash mismatch'):
                saved.process_saved(p, base)

    def test_rejects_wrong_exhibition_region_and_missing_late_entry(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = packet(base, 'green_pedestrian_present')
            rows = json.loads((base / 'events.json').read_text())
            rows[0]['other_users'][0]['xy'] = [0, 4]
            p['event_ref'] = ref(base, 'events.json', rows)
            with self.assertRaisesRegex(saved.SourceError, 'differs at exhibition'):
                saved.process_saved(p, base)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = packet(base, 'green_pedestrian_late')
            rows = json.loads((base / 'events.json').read_text())
            for row in rows[1:]:
                row['other_users'][0]['xy'] = [0, 4]
            p['event_ref'] = ref(base, 'events.json', rows)
            with self.assertRaisesRegex(saved.SourceError, 'never enters'):
                saved.process_saved(p, base)

    def test_rejects_phase_and_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = packet(base, 'green_clear')
            with self.assertRaisesRegex(saved.SourceError, 'duration differs'):
                saved.process_saved({**p, 'duration_frames': 4}, base)
            rows = json.loads((base / 'events.json').read_text())
            rows[1]['lit_aspects'] = ['circular_green', 'green_arrow']
            p['event_ref'] = ref(base, 'events.json', rows)
            with self.assertRaisesRegex(saved.SourceError, 'not evidenced throughout'):
                saved.process_saved(p, base)
