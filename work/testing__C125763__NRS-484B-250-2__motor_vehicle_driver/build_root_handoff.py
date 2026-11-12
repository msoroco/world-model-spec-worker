"""Materialize the package-level Native handoff from the proved primary bundle."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = manifest['cases'][0]
    construction = copy.deepcopy(json.loads((HERE / entry['construction']).read_text()))
    config_row = next(row for row in construction['files'] if row['path'] == 'config.json')
    config = json.loads(config_row['content'])
    config['supported_case_ids'] = [row['case_id'] for row in manifest['cases']]
    config['cameras'] = [
        {'name': name, 'width': width, 'height': height,
         'pose_strategy': 'reviewed site camera pose with original Native frame join',
         'fov_deg': 90}
        for name, width, height in CAMERAS]
    write(HERE / 'config.json', config)
    config_row['content'] = (HERE / 'config.json').read_text()
    bundle_test = next(row for row in construction['files']
                       if row['path'] == 'tests/test_bundle.py')
    bundle_test['content'] = bundle_test['content'].replace(
        'import unittest\n', 'import unittest\nfrom pathlib import Path\n').replace(
        'load_config("config.json")',
        'load_config(str(Path(__file__).resolve().parents[1] / "config.json"))')
    construction['static_checks'] = [
        'Native map, entrance lane and governing yield sign match reviewed site packet',
        'Both distinct Native vehicle bodies and four camera frames join every world tick',
    ]
    construction['termination_rules'] = [
        'Capture configured 60 synchronized original frames and seal only after encoders close and world restoration succeeds',
        'Reject failed or incomplete Native capture before owner release',
    ]
    construction['mechanisms'] = [
        'Native two-vehicle route and yield controllers in native_pair.py',
        'Original complete-body crossing history and four named source videos in capture_sources.py',
        'Source-bound physical completion and recorded-only finalization',
    ]
    for row in construction['files']:
        if row.get('source'):
            continue
        target = HERE / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text() != row['content'] and row['path'] != 'tests/test_bundle.py':
            raise ValueError('Root handoff file differs: ' + row['path'])
        target.write_text(row['content'])
    write(HERE / 'construction.json', construction)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': config['duration_s'],
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'both vehicles, median crossing and governing yield sign',
             'interval': 'startup through complete exit'},
            {'view': 'approach', 'subject': 'ego yield entrance and approach body',
             'interval': 'startup through complete exit'},
            {'view': 'reference_corner', 'subject': 'other approach and crossing conflict area',
             'interval': 'startup through complete exit'},
            {'view': 'driver_reference', 'subject': 'ego driver reference and governing entrance',
             'interval': 'startup through complete exit'},
        ],
        'limitations': ['Prospective camera placement; Native visibility and sign legibility require physical review'],
    }
    terms = {
        'st.intersection': ('site_packet.py', 'Reviewed site packet and Native map/intersection ID'),
        'st.lane_enters': ('capture_sources.py', 'Original Native road/lane IDs for both complete bodies'),
        'drv.entering_intersection': ('capture_sources.py', 'Complete body vertices per original Native frame'),
        'drv.arrival_order': ('finalizer.py', 'Body entry frames and entry-time difference; legal tolerance unresolved'),
        'rel.bearing': ('capture_sources.py', 'Both original positions and approach forward vectors; right-side relation requires site review'),
        'drv.yields_to': ('native_pair.py', 'Original controller speed/brake and conflict hold; legal yielding unresolved'),
        'dev.traffic_signal': ('site_packet.py', 'Governance source review; actual official device status remains unverified'),
        'drv.turning': ('runner.py', 'Opposite-direction left-turn controller intention and Native route history'),
    }
    plan['source_observation_mapping'] = {
        term: {'evidence': evidence, 'channels': ['entry_timing'] if term == 'drv.arrival_order' else [],
               'source_refs': [source]}
        for term, (source, evidence) in terms.items()}
    write(plan_path, plan)
    print('root config, construction, camera plan and eight source mappings written')


if __name__ == '__main__':
    main()
