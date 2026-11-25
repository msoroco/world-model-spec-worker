"""Build three exact diagnostic towing sweep bundles without touching prior cases."""
import copy
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from caravan_spacing_geometry import plan

PREFIX = 'caravan_spacing_towed_physical-'
POINTS = ((3.0, 'stop_before'), (10.0, 'occupy'), (6.5, 'occupy'))


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + old[:60])
    return text.replace(old, new)


def write_source(name, text):
    path = PACKAGE / name
    path.write_text(text)
    return 'work/' + PACKAGE.name + '/' + name


def source_variants():
    native = (PACKAGE / 'caravan_towing_native.py').read_text()
    mapping = 'CASES = {' + ',\n         '.join(
        repr(PREFIX + str(i).zfill(4)) + ': ' + repr(outcome)
        for i, (_, outcome) in enumerate(POINTS)) + '}'
    native = replace_once(native,
        'CASES = {ASSIGNMENT + "__towed_entrant_can_occupy_gap": "occupy"}', mapping)
    native_source = write_source('caravan_towing_sweep_native.py', native)
    saved = (PACKAGE / 'caravan_towing_saved.py').read_text()
    ids = tuple(PREFIX + str(i).zfill(4) for i in range(len(POINTS)))
    saved = replace_once(saved,
        "CASE_ID = WIDE.replace('__entrant_can_occupy_gap', '__towed_entrant_can_occupy_gap')",
        'CASE_IDS = ' + repr(ids) + '\nOUTCOMES = ' +
        repr({case_id: outcome for case_id, (_, outcome) in zip(ids, POINTS)}))
    saved = replace_once(saved, 'if case_id != CASE_ID:', 'if case_id not in CASE_IDS:')
    saved = replace_once(saved, 'from caravan_saved import WIDE, finalize as analyze_entry',
                         'from caravan_saved import WIDE, NARROW, finalize as analyze_entry')
    saved = replace_once(saved, 'entry = analyze_entry(root, WIDE, minimum_frames=minimum_frames)',
        "entry = analyze_entry(root, WIDE if OUTCOMES[case_id] == 'occupy' else NARROW, minimum_frames=minimum_frames)")
    saved = replace_once(saved, "'entry_observed': entry['wide_gap_entry_observed'],",
        "'entry_observed': entry['wide_gap_entry_observed'] if OUTCOMES[case_id] == 'occupy' else False,")
    saved_source = write_source('caravan_towing_sweep_saved.py', saved)
    finalizer = (PACKAGE / 'caravan_towing_finalizer.py').read_text()
    finalizer = replace_once(finalizer,
        'from caravan_towing_saved import CASE_ID, finalize as observe',
        'from caravan_towing_sweep_saved import CASE_IDS, OUTCOMES, finalize as observe')
    finalizer = replace_once(finalizer, 'if case_id != CASE_ID:', 'if case_id not in CASE_IDS:')
    finalizer = replace_once(finalizer, 'expected = True',
                             "expected = OUTCOMES[case_id] == 'occupy'")
    finalizer_source = write_source('caravan_towing_sweep_finalizer.py', finalizer)
    return native_source, saved_source, finalizer_source


def build():
    native_source, saved_source, finalizer_source = source_variants()
    base_path = PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json'
    base = json.loads(base_path.read_text())
    packet = json.loads(next(item['content'] for item in base['files']
                             if item['path'] == 'site_packet.json'))
    outputs = []
    for i, (spacing, outcome) in enumerate(POINTS):
        case_id = PREFIX + str(i).zfill(4)
        variant, geometry = plan(packet, spacing)
        if geometry['planned_outcome'] != outcome:
            raise ValueError('Sweep geometry changed outcome')
        construction = copy.deepcopy(base)
        construction['case_id'] = case_id
        construction['mechanisms']['diagnostic_member_spacing_m'] = spacing
        construction['mechanisms']['entry_outcome'] = outcome
        construction['mechanisms']['note'] = 'Exact CPU diagnostic sweep plan; not selected delivery.'
        for item in construction['files']:
            name = item['path']
            if name in ('runner.py', 'caravan_towing_native.py'):
                item['content'] = (PACKAGE / 'caravan_towing_sweep_native.py').read_text()
                item['source'] = native_source
                if name == 'caravan_towing_native.py':
                    item['path'] = 'caravan_towing_sweep_native.py'
            elif name in ('finalizer.py', 'caravan_towing_finalizer.py'):
                item['content'] = (PACKAGE / 'caravan_towing_sweep_finalizer.py').read_text()
                item['source'] = finalizer_source
                if name == 'caravan_towing_finalizer.py':
                    item['path'] = 'caravan_towing_sweep_finalizer.py'
            elif name == 'caravan_towing_saved.py':
                item['content'] = (PACKAGE / 'caravan_towing_sweep_saved.py').read_text()
                item['source'] = saved_source
                item['path'] = 'caravan_towing_sweep_saved.py'
            elif name == 'site_packet.json':
                item['content'] = json.dumps(variant, indent=2) + '\n'
            elif name == 'tests/test_offline.py':
                item['content'] = (
                    'import json, unittest\n'
                    'from pathlib import Path\n'
                    'import caravan_towing_sweep_native as native\n'
                    'from caravan_capture import validate_site\n'
                    'class Offline(unittest.TestCase):\n'
                    ' def test_exact_identity_and_unreviewed_site_guard(self):\n'
                    '  root=Path(__file__).resolve().parents[1]\n'
                    '  config=json.loads((root/"config.json").read_text())\n'
                    '  assert config["selected_case_id"]==' + repr(case_id) + '\n'
                    '  assert config["duration_s"]==45 and config["rate_hz"]==20\n'
                    '  assert len(config["cameras"])==4\n'
                    '  packet=json.loads((root/"site_packet.json").read_text())\n'
                    '  assert packet["site_review_status"]=="diagnostic_unreviewed"\n'
                    '  with self.assertRaisesRegex(ValueError,"Reviewed Native caravan site required"):\n'
                    '   validate_site(packet,root,packet["native_map_id"])\n'
                    '  assert native.CASES[config["selected_case_id"]]==' + repr(outcome) + '\n'
                    'if __name__=="__main__": unittest.main()\n')
            elif name == 'config.json':
                config = json.loads(item['content'])
                config['selected_case_id'] = case_id
                config['supported_case_ids'] = [case_id]
                config['case']['case_id'] = case_id
                config['authored_member_center_spacing_m'] = spacing
                if outcome == 'stop_before':
                    config['physical_completion'] = {
                        'body_key': 'participants.entrant.body_vertices_m',
                        'context_sources': ['caravan_context.json'],
                        'criterion': 'travel_progress', 'minimum_progress_m': 2,
                        'motion_source': 'caravan_history.jsonl'}
                item['content'] = json.dumps(config, indent=2) + '\n'
        path = PACKAGE / 'cases' / (case_id + '-construction.json')
        path.write_text(json.dumps(construction, indent=2) + '\n')
        outputs.append({'case_id': case_id, 'construction': 'cases/' + path.name,
                        'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'spacing_m': spacing, 'planned_outcome': outcome})
    index = PACKAGE / 'cases/towing-sweep-constructions.json'
    index.write_text(json.dumps({'format': 'worker-towing-sweep-construction-index',
                                 'selected_for_delivery': False,
                                 'cases': outputs}, indent=2) + '\n')
    print(json.dumps({'construction_count': len(outputs), 'case_ids': [x['case_id'] for x in outputs]}))


if __name__ == '__main__':
    build()
