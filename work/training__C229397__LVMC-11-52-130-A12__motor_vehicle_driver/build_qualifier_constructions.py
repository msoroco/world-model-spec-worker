"""Build exact, unselected qualifier candidate constructions from reviewed sources."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
BASE = json.loads((HERE / 'draft-crosswalk/controlled_2/primary/construction.json').read_text())
SUFFIXES = ('traffic_conflict_near', 'law_compliance_near',
            'police_direction_near', 'device_direction_near')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(suffix):
    case_id = ASSIGNMENT + '__' + suffix
    construction = json.loads(json.dumps(BASE))
    construction['case_id'] = case_id
    construction['mechanisms'] = [
        'subject park target remains three metres before proposed crosswalk',
        'Native qualifier context acquired independently at each of 600 frames',
        'statutory necessity or direction remains source reviewed and unresolved']
    construction['status'] = 'qualifier_cpu_candidate_original_source_pending'
    files = {item['path']: item for item in construction['files']}
    for name in ('qualifier_runner.py', 'qualifier_geometry.py',
                 'qualifier_context.py', 'geometry.py',
                 'qualifier_source_audit.py'):
        source = HERE / ('native' if name in (
            'qualifier_runner.py', 'qualifier_geometry.py',
            'qualifier_context.py', 'geometry.py') else '') / name
        target = 'runner.py' if name == 'qualifier_runner.py' else name
        files[target] = {'path': target, 'content': source.read_text()}
    finalizer = files['finalize_delivery.py']['content'].replace(
        "'stand_near': 3.0}[config['crosswalk_case']]",
        "'stand_near': 3.0, 'traffic_conflict_near': 3.0, "
        "'law_compliance_near': 3.0, 'police_direction_near': 3.0, "
        "'device_direction_near': 3.0}[config['crosswalk_case']]")
    finalizer = finalizer.replace(
        'from finalize_crosswalk import finalize as diagnose',
        'from finalize_crosswalk import finalize as diagnose\n'
        'from qualifier_source_audit import audit as audit_qualifier')
    finalizer = finalizer.replace(
        'def finalize(attempt, output):',
        "def measure_qualifier_context(review, sources):\n"
        "    return {'value': {'qualifier': review['qualifier'],\n"
        "                      'finding': review['finding'],\n"
        "                      'source_frame_count': review['source_frame_count']},\n"
        "            'method': 'measure_qualifier_context', 'sources': sources}\n\n\n"
        'def finalize(attempt, output):')
    finalizer = finalizer.replace(
        '    diagnostic = diagnose(attempt)',
        "    qualifier_name = config['crosswalk_case'].removesuffix('_near')\n"
        "    packet_path = attempt / 'qualifier-source-packet.json'\n"
        "    if not packet_path.is_file():\n"
        "        raise ValueError('Missing original qualifier source packet')\n"
        "    packet = json.loads(packet_path.read_text())\n"
        "    qualifier_review = audit_qualifier(attempt, packet_path, case_id, qualifier_name,\n"
        "        diagnostic=packet.get('diagnostic_fixture') is True)\n"
        "    diagnostic = diagnose(attempt)")
    source_file = ('traffic-actors.jsonl' if suffix == 'traffic_conflict_near'
                   else 'device-states.jsonl' if suffix == 'device_direction_near'
                   else 'authority-events.jsonl')
    finalizer = finalizer.replace(
        "'crosswalk-inventory.json', 'crosswalk-source-review.json')",
        "'crosswalk-inventory.json', 'crosswalk-source-review.json',\n"
        "                    'qualifier-context.json', '" + source_file + "', 'qualifier-source-packet.json')")
    finalizer = finalizer.replace(
        '    for name, items in values.items():',
        "    context_rows = [json.loads(line) for line in (attempt / '" + source_file + "').read_text().splitlines()]\n"
        "    if len(context_rows) != len(mapping):\n"
        "        raise ValueError('Qualifier context frame count differs')\n"
        "    values['" + ('traffic_actor_motion' if suffix == 'traffic_conflict_near'
                         else 'device_state' if suffix == 'device_direction_near'
                         else 'authority_timeline') + "'] = context_rows\n"
        '    for name, items in values.items():')
    finalizer = finalizer.replace(
        "'diagnostic': diagnostic, 'source_sha256': sources,",
        "'diagnostic': diagnostic, 'qualifier_source_review': qualifier_review,\n"
        "              'source_sha256': sources,")
    finalizer = finalizer.replace(
        "'measurements': {'crosswalk_position': measurement},",
        "'measurements': {'crosswalk_position': measurement,\n"
        "                  'qualifier_context': measure_qualifier_context(qualifier_review,\n"
        "                      {name: sources[name] for name in ('" + source_file + "',\n"
        "                       'qualifier-source-packet.json')})},")
    files['finalize_delivery.py']['content'] = finalizer
    files['tests/test_native.py']['content'] = (
        "import unittest\nimport runner\nfrom qualifier_geometry import open_drive\n\n"
        "class TestQualifier(unittest.TestCase):\n"
        "    def test_native_plan(self):\n"
        "        self.assertTrue(runner.check()['passed'])\n"
        "        self.assertIn('OpenDRIVE', open_drive('" + suffix + "'))\n")
    config = json.loads(files['config.json']['content'])
    config['case_id'] = config['selected_case_id'] = case_id
    config['case']['case_id'] = case_id
    config['supported_case_ids'] = [case_id]
    config['crosswalk_case'] = suffix
    config['required_atoms'] = []
    name = ('traffic_actor_motion' if suffix == 'traffic_conflict_near'
            else 'device_state' if suffix == 'device_direction_near'
            else 'authority_timeline')
    method = ('original Native second vehicle trajectory' if suffix == 'traffic_conflict_near'
              else 'original Native traffic-control device readback or explicit absence'
              if suffix == 'device_direction_near' else
              'original Native frame join; legal authority requires separate authenticated source')
    channel = {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
               'method': method, 'time_window': '600 frames',
               'reference_frame': 'Native frame identity',
               'uncertainty': 'authority and statutory applicability require independent review'}
    config['recording_description']['channels'].append(channel)
    construction['recording_description']['channels'].append(channel)
    config['recording_description']['limitations'].append(
        'Qualifier finding remains unresolved pending original authority or necessity review')
    construction['recording_description']['limitations'].append(
        'Qualifier finding remains unresolved pending original authority or necessity review')
    config['case']['recording_description'] = config['recording_description']
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    construction['files'] = list(files.values())
    construction['measurement_plan']['required_sources'].extend([
        'qualifier-context.json',
        source_file,
        'qualifier-source-packet.json'])
    target = HERE / 'draft-qualifiers' / suffix / 'primary'
    target.mkdir(parents=True, exist_ok=True)
    path = target / 'construction.json'
    path.write_text(json.dumps(construction, indent=2) + '\n')
    return {'case_id': case_id, 'construction': str(path.relative_to(HERE)),
            'sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in SUFFIXES], sort_keys=True))
