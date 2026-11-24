"""Independent current-runtime primary offline and controlled-request audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c111294-2502-tmp'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    frozen = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan = CASE / 'case-plan.json'
    source = json.loads(frozen.read_text())
    planned = json.loads(plan.read_text())
    if (sha(frozen) != 'd005cde0eec41f63fcc0dc8aedb3a3d81c39daa3ed8b2d193fca4161769dd738' or
            source['law']['text'] != planned['source_law']['text'] or
            source['cell']['control'] != 'other_vehicle'):
        raise ValueError('current frozen law/cell source differs')
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    if manifest.get('status') != 'draft_not_selected' or len(manifest.get('cases', [])) != 2:
        raise ValueError('unselected two-case manifest required')
    tracks = {}
    checked = 0
    for case in manifest['cases']:
        suffix = case['case_id'].split('__')[-1]
        if suffix not in ('controlled_1', 'controlled_2'):
            raise ValueError('unexpected exact case')
        choices = [{'id': 'primary', 'construction': case['construction'],
                    'construction_sha256': case['construction_sha256']}] + case['candidates']
        if {c['id'] for c in choices} != {'primary', 'fallback1', 'fallback2', 'fallback3'}:
            raise ValueError('candidate inventory changed')
        for choice in choices:
            path = HERE / choice['construction']
            if sha(path) != choice['construction_sha256']:
                raise ValueError('construction hash differs')
            construction = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            if (construction['status'] != 'unselected_cpu_diagnostic' or
                    files['assignment-source.json'].encode() != frozen.read_bytes() or
                    files['case-plan.json'].encode() != plan.read_bytes()):
                raise ValueError('copied source or selection status differs')
            checked += 1
        bundle = HERE / 'drafts' / suffix / 'primary'
        config = json.loads((bundle / 'config.json').read_text())
        if (config['assignment_sha256'] != sha(frozen) or
                config['source_text'] != source['law']['text'] or
                config['ego_highway_road_ids'] != [250, 251, 252] or
                config['right_other_highway_road_ids'] != [253, 254, 255]):
            raise ValueError('primary law/highway request differs')
        rows = [json.loads(line) for line in
                (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
        if len(rows) != 600 or any(row['frame'] != i or row['time_s'] != i / 20 or
                                   row['authored_official_device_count'] != 0
                                   for i, row in enumerate(rows)):
            raise ValueError('30-second uncontrolled request differs')
        tracks[suffix] = rows
        output = SCRATCH / ('current-primary' if suffix == 'controlled_1' else 'current-primary-2')
        selection = json.loads((output / 'candidate-selection.json').read_text())
        if selection.get('candidate_id') != 'primary':
            raise ValueError('current offline candidate differs')
        log = (output / 'offline.log').read_text()
        if 'Ran 4 tests' not in log or 'OK' not in log:
            raise ValueError('current offline tests missing')
    left, right = tracks['controlled_1'], tracks['controlled_2']
    if [r['requested_other_xyz_m'] for r in left] != [r['requested_other_xyz_m'] for r in right]:
        raise ValueError('right-hand vehicle changed across pair')
    changed = [i for i, (a, b) in enumerate(zip(left, right))
               if a['requested_ego_xyz_m'] != b['requested_ego_xyz_m']]
    if not changed or any(a['requested_ego_heading_rad'] != b['requested_ego_heading_rad']
                          for a, b in zip(left, right)):
        raise ValueError('controlled ego timing request absent or route changed')
    result = {'format': 'c111294-2502-current-primary-audit-v1',
              'assignment_sha256': sha(frozen), 'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
              'constructions_hashed': checked, 'current_offline_primary_cases': 2,
              'controlled_ego_request_changed_frames': len(changed),
              'right_vehicle_request_fixed': True, 'authored_official_devices': 0,
              'physical_entry_observed': False, 'statutory_verdict': None,
              'delivery_ready': False}
    path = HERE / 'current-primary-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
