"""Materialize the reviewed 400(2)(a) pilot handoff from exact input and runtime contracts."""
import copy
import hashlib
import json
import pathlib
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
AID = 'testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
FOLDER = ROOT / 'work' / AID
SOURCE = ROOT / 'migration-candidates' / AID


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((SOURCE / 'case-plan.json').read_text())
    assert plan['law_id'] == assignment['law']['id'] == 'NRS-484B-400-2a'
    assert plan['cell_id'] == assignment['cell_id'] == 'C109705'
    assert len(plan['cases']) == 3
    assert [c['target_type'] for c in plan['cases']] == ['baseline', 'compliant_attempt', 'violating_attempt']
    # Candidate provenance points at the retired runtime and shared files.
    # Bind this return to the exact, available inputs instead.
    plan['sources'] = [{'path': rel, 'sha256': sha(ROOT / rel)} for rel in [
        'inputs/' + AID + '/assignment.json',
        'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'examples/intersection/native/scene-stop257-v1.xodr',
        'updates/004.json',
        'skills/worker-preparation/SKILL.md']]
    for case in plan['cases']:
        assert case['variable_assignments']['authored_context']['value']['two_directional_highways'] is True
        assert case['variable_assignments']['commanded_turn_path']['value'] == 'left_turn'
    write(FOLDER / 'case-plan.json', plan)
    cfgbase = json.loads((SOURCE / 'config.json').read_text())
    assert cfgbase['cameras'][0]['width'] == 1920 and len(cfgbase['cameras']) == 4
    # Retain the reviewed lane widths and junction geometry, removing stop control
    # because 400(2)(a) does not require it. Native turn connectivity is a live
    # capability question and is reported by the measurement script.
    tree = ET.parse(ROOT / 'examples/intersection/native/scene-stop257-v1.xodr')
    maproot = tree.getroot()
    for signals in maproot.findall('.//signals'):
        signals.clear()
    for objects in maproot.findall('.//objects'):
        objects.clear()
    maproot.find('header').set('name', 'C109705-two-directional-left-turn')
    # A native quarter-circle connector joins the eastbound right-half lanes to
    # the northbound right-half lanes. The historical stop map had through
    # connectors only and therefore could not establish this turn topology.
    connector = ET.fromstring('''<road name="left_turn_west_to_north" id="13" length="10.9955742876" junction="100">
      <link><predecessor elementType="road" elementId="1" contactPoint="end"/><successor elementType="road" elementId="4" contactPoint="start"/></link>
      <planView><geometry s="0" x="-7" y="0" hdg="0" length="10.9955742876"><arc curvature="0.142857142857"/></geometry></planView>
      <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile><lateralProfile/>
      <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><left/>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="yellow" width=".12" laneChange="none"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane>
      <lane id="-2" type="driving" level="false"><link><predecessor id="-2"/><successor id="-2"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects/><signals/>
      </road>''')
    maproot.insert(len(maproot.findall('road')) + 1, connector)
    junction = maproot.find('junction')
    junction.append(ET.fromstring('''<connection id="4" incomingRoad="1" connectingRoad="13" contactPoint="start">
      <laneLink from="-1" to="-1"/><laneLink from="-2" to="-2"/></connection>'''))
    (FOLDER / 'intersection.xodr').write_text(ET.tostring(maproot, encoding='unicode'))
    cases = copy.deepcopy(plan['cases'])
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'cases': cases, 'sweep_specs': [], 'sweeps_expanded': True}
    write(FOLDER / 'proposals/cases.json', proposal)
    runner = (FOLDER / 'runner.py').read_text()
    analysis = (FOLDER / 'analyze.py').read_text()
    xodr = (FOLDER / 'intersection.xodr').read_text()
    tests = '''import json\nimport unittest\nfrom pathlib import Path\nimport runner\nclass PilotTests(unittest.TestCase):\n def test_route_is_continuous_and_within_road(self):\n  runner.check()\n  for lateral in (1.75,5.25):\n   points=runner.route(lateral)\n   self.assertTrue(all(abs(x1-x0)<=1.5 and abs(y1-y0)<=1.5 for (x0,y0),(x1,y1) in zip(points,points[1:])))\n'''
    (FOLDER / 'tests').mkdir(exist_ok=True)
    (FOLDER / 'tests/test_pilot.py').write_text(tests)
    entries = []
    for case in cases[1:]:
        cfg = copy.deepcopy(cfgbase)
        cfg['case'] = case
        cfg['selected_case_id'] = case['case_id']
        cfg['observations'] = plan['observations']
        cfg['required_atoms'] = [x['name'] for x in plan['observations'] if x.get('mandatory', True)]
        cfg['max_ticks'] = 600
        cfg['authored_test_context'] = {'core_assumptions': [
            'Public dedication and public vehicular access are synthetic assumptions.',
            'The junction is a non-alley intersection of two-directional undivided highways.']}
        cfg['public_way_road_ids'] = [1, 2, 3, 4]
        construction = {'case_id': case['case_id'], 'cell_id': assignment['cell_id'],
            'actor': assignment['actor'], 'entrypoint': 'runner.py',
            'recording_description': case['recording_description'],
            'measurement_plan': {'source': 'physical_samples.jsonl', 'approach_window': 'x<-11 m',
                                 'target_lateral_m': case['variable_assignments']['commanded_approach_lateral']['value'],
                                 'reference': 'native centerline y=0 and full body vertices'},
            'static_checks': ['OpenDRIVE parsed', 'two-way lanes', 'route geometry', 'camera resolution', 'mandatory channels'],
            'termination_rules': {'max_ticks': 600, 'success': 'last route waypoint reached at speed <2 m/s',
                                  'failure': 'exception or incomplete maneuver'},
            'mechanisms': {'road': 'authored OpenDRIVE, exact inline file',
                           'controller': 'native VehicleControl route tracking, 20 Hz',
                           'capture': 'supplied PipelineCapture, native all actor observations'},
            'files': [
                {'path': 'runner.py', 'content': runner, 'source': 'work/' + AID + '/runner.py'},
                {'path': 'analyze.py', 'content': analysis, 'source': 'work/' + AID + '/analyze.py'},
                {'path': 'intersection.xodr', 'content': xodr, 'source': 'work/' + AID + '/intersection.xodr'},
                {'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'},
                {'path': 'tests/test_pilot.py', 'content': tests, 'source': 'work/' + AID + '/tests/test_pilot.py'}]}
        rel = 'constructions/' + case['case_id'] + '.json'
        write(FOLDER / rel, construction)
        entries.append({'case_id': case['case_id'], 'kind': 'capability', 'construction': rel,
                        'construction_sha256': sha(FOLDER / rel),
                        'measurement_procedure': {'entrypoint': 'analyze.py', 'output_schema': 'pilot-capability-report-v1'}})
        if case is cases[1]:
            write(FOLDER / 'config.json', cfg)
            write(FOLDER / 'construction.json', construction)
    runtime_sha = sha(ROOT / 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json')
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
          'assignment_id': AID, 'runtime_manifest_sha256': runtime_sha, 'cases': entries})
    tested = []
    for case, attempt in [(cases[1], 'pilot-attempt-0l'), (cases[2], 'pilot-attempt-1j')]:
        source = ROOT / '.runtime-work' / attempt / 'offline.log'
        if source.is_file():
            rel = 'tests/' + attempt + '.log'
            (FOLDER / rel).write_bytes(source.read_bytes())
            tested.append({'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID +
                '/execution-manifest.json --case ' + case['case_id'] + ' --output .runtime-work/' + attempt,
                'exit_code': 0, 'log': rel, 'sha256': sha(FOLDER / rel)})
    if len(tested) == 2:
        write(FOLDER / 'result.json', {'assignment_id': AID,
              'input_sha256': sha(ROOT / 'inputs' / AID / 'assignment.json'),
              'status': 'ready', 'readiness_kind': 'capability', 'applied_update': 4,
              'tests': tested, 'physical_acceptance': False})
    (FOLDER / 'HANDOFF.md').write_text('''# 400(2)(a) pilot capability handoff\n\nTwo exact nonbaseline cases compare inner and outer approach positions on a two-directional synthetic intersection. The baseline is a definition only. The exact input law and witness govern; public dedication, access, and non-alley status remain explicit synthetic assumptions.\n\nThe shared runtime selftest passed separately. Run the exact cases with `runtime.py offline` using execution-manifest.json. A later operator may run `runtime.py capture` against an already-owned CARLA endpoint, then `analyze.py --attempt PATH --output REPORT` on the retained native samples. Capture uses the supplied PipelineCapture; conversion/rendering remain the supplied runtime process/render commands. No simulator was run here.\n\nCapability questions: native map turn continuity, ego controller tracking, right-half full footprint, four-view visibility, final duration and delivered channel coverage. The capability report requests repair at the same frozen setting if measured motion fails. No physical or legal acceptance is claimed.\n''')


if __name__ == '__main__':
    main()
