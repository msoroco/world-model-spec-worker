"""Rebind the selected CPU matrix to the canonical original Native runner."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREFIX = f'work/{HERE.name}/native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    cases = []
    for suffix in ('controlled_1', 'controlled_2'):
        case_id = HERE.name + '__' + suffix
        choices = []
        for candidate in ('primary', 'fallback1', 'fallback2'):
            source = HERE / 'selected-v3' / suffix / candidate / 'construction.json'
            construction = json.loads(source.read_text())
            capture = next(item for item in construction['files']
                           if item['path'] == PREFIX + '/capture.py')
            capture['content'] = (HERE / 'native/capture.py').read_text()
            construction['files'].append({'path': 'runner.py', 'content': (HERE / 'runner.py').read_text()})
            construction['entrypoint'] = 'runner.py'
            construction['mechanisms'] = {
                'construction_status': 'selected_cpu_prepared_original_unverified',
                'road': 'Six connected authored OpenDRIVE road regions and two crossing approaches',
                'actors': 'Original CARLA ego and right-side other vehicle',
                'capture': 'Four synchronized RGB views, original actor bodies and raw graph handoff'}
            construction['measurement_plan'] = {
                'method': 'Source-joined body-front entry and rear exit per retained original frame',
                'duration_s': 30, 'rate_hz': 20,
                'legal_verdict': None}
            construction['static_checks'] = [
                {'name': 'authored_source_and_trajectory', 'status': 'passed_cpu_request'},
                {'name': 'original_world_lanes_and_governance', 'status': 'pending_original_capture'}]
            construction['termination_rules'] = {
                'planned_frame_count': 600,
                'on_failure': 'retain capture report, close encoders, restore owned world state',
                'acceptance': 'defer physical and legal review to original evidence'}
            target = HERE / 'selected-v4' / suffix / candidate / 'construction.json'
            write(target, construction)
            if candidate == 'primary':
                primary = target
            else:
                metric = ('absolute_ego_other_entry_gap_s' if candidate == 'fallback1'
                          else 'all_participants_visible')
                choices.append({
                    'id': candidate,
                    'construction': str(target.relative_to(HERE)),
                    'construction_sha256': sha(target),
                    'trigger': {
                        'source': ('original actor body entry times' if candidate == 'fallback1'
                                   else 'original overview and detail pixels'),
                        'metric': metric,
                        'failure_condition': ('< 1.5 s or missing' if candidate == 'fallback1'
                                              else 'false or unreviewed')},
                    'changed_knobs': (['requested_speed_mps'] if candidate == 'fallback1'
                                      else ['camera_policy'])})
        cases.append({
            'case_id': case_id, 'kind': 'delivery',
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Original entry timing or four-view participant coverage may fail measurable checks'},
            'construction': str(primary.relative_to(HERE)),
            'construction_sha256': sha(primary),
            'candidates': choices,
            'fixture_recipe': str((HERE / 'selected-v3' / suffix / 'primary' /
                                   'fixture-recipe.json').relative_to(REPO)),
            'measurement_contract': str(Path('selected-v3') / suffix / 'primary' /
                                        'measurement-contract.json'),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
        })
    runtime = json.loads((REPO / 'batch.json').read_text())
    manifest = HERE / 'selected-v4-manifest.json'
    write(manifest, {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': runtime['runtime']['source_manifest_sha256'],
        'status': 'selected_cpu_in_progress',
        'cases': cases,
    })
    print(json.dumps({'manifest_sha256': sha(manifest), 'candidate_constructions': 6}))


if __name__ == '__main__':
    build()
